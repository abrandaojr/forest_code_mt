"""Audit CAR intersections and render paginated maps of effective inputs."""
from __future__ import annotations
import json, math, re, textwrap
from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib as mpl
import pandas as pd
import pyarrow.parquet as pq
import shapely
import _00_paths as paths

ROOT, PRE, QA, FIG, DATE = paths.ROOT, paths.PRE, paths.QC, paths.FIGURES, paths.RUN_DATE
mpl.rcParams.update({"font.family": "Arial", "font.size": 12, "axes.titlesize": 12})
MAPS_PER_PANEL = 4
NAMES = {
 "app":"Declared APP", "app_fnl_auas":"Final APP — post-2008 land use", "app_fnl_avn24":"Final APP — 2024 native vegetation",
 "app_fnl_cs00":"Final APP — consolidated area 2000", "app_fnl_cs08":"Final APP — consolidated area 2008",
 "appd_1a2mf_cs08":"Degraded APP — 1–2 fiscal modules", "appd_2a4mf_cs08":"Degraded APP — 2–4 fiscal modules",
 "appd_4a10mf_cs08":"Degraded APP — 4–10 fiscal modules", "appd_gt10mf_cs08":"Degraded APP — over 10 fiscal modules",
 "appd_lte1mf_cs08":"Degraded APP — up to 1 fiscal module", "appd_declared_ha":"Declared degraded APP",
 "apprl_declared_ha":"APP within Legal Reserve", "arl_declared_ha":"Declared Legal Reserve",
 "arld_declared_ha":"Degraded Legal Reserve", "au_declared_ha":"Declared alternative land use",
 "auas_post2008":"Post-2008 alternative land use", "avn_declared_ha":"Declared native vegetation",
 "car_atp":"Total property area (CAR)", "cons_area_2000":"Consolidated area in 2000", "cons_area_2008":"Consolidated area in 2008",
 "native_veg_2024":"Native vegetation in 2024", "native_veg_x_radam":"Native vegetation × RADAM",
 "nveg_radam":"Native vegetation by physiognomy", "radam":"RADAMBRASIL — applied classification",
 "nascente":"Springs", "utilidade_publica":"Public utility areas", "assentamentos":"Settlements",
 "assentamentos_intermat":"INTERMAT settlements", "quilombolas":"Quilombola territories",
 "terras_indigenas":"Indigenous lands", "unidades_conservacao":"Protected areas", "area_declividade":"Steep-slope areas",
 "area_inundada":"Flooded areas", "area_topo_morro":"Hilltops", "area_umida":"Wetlands", "borda_chapada":"Plateau edges",
 "interesse_social":"Social-interest areas", "lagoa_natural":"Natural lakes", "manguezal":"Mangroves",
 "reservatorio_artificial":"Artificial reservoirs", "restinga":"Restinga vegetation", "rio_10_a_50":"Rivers 10–50 m wide",
}

def load_inventory():
 frames=[]
 for source in ("car_validated","car_digital","car_proxy"):
  folder=PRE/source
  meta=pd.DataFrame(json.loads((folder/"layers_meta.json").read_text(encoding="utf-8")))
  match=pd.read_csv(folder/f"match_table_{DATE}.csv")
  meta["effective_layer"]=meta["short"]
  meta.loc[meta["is_radam"].fillna(False),"effective_layer"]="radam"
  meta.loc[meta["is_nveg_radam"].fillna(False),"effective_layer"]="nveg_radam"
  joined=match.merge(meta.drop_duplicates("effective_layer",keep="last"),left_on="layer",right_on="effective_layer",how="left")
  if source=="car_validated":
   mask=joined["layer"].eq("radam")
   joined.loc[mask,"path"]=str(ROOT/"data/proc/simcar_validado/radam_full_coverage_x_car_atp.parquet")
   joined.loc[mask,"label"]="RADAM estadual × CAR (cobertura integral)"
  joined.insert(0,"source_universe",source); frames.append(joined)
 audit=pd.concat(frames,ignore_index=True)
 audit["coverage_expectation"]=audit["layer"].map(lambda x:"Exhaustive (>=99.9%)" if x=="radam" else "Thematic")
 audit["audit_status"]="PASS"
 audit.loc[audit["layer"].eq("radam")&audit["pct_match"].lt(99.9),"audit_status"]="FAIL: partial exhaustive layer"
 audit.loc[audit["matched"].isna(),"audit_status"]="FAIL: not joined"
 return audit

def map_key(value):
 value=re.sub(r"_x_car_atp(?:_fnl)?$","",str(value))
 while re.search(r"_(?:net|max)$",value): value=re.sub(r"_(?:net|max)$","",value)
 if value.startswith("vegetacao_radambrasil"): return "radam"
 return value

def state_boundary():
 state=gpd.read_parquet(ROOT/"data/raw/reference_maps/lml_unidade_federacao_a.parquet")
 for c in state.columns:
  if c!=state.geometry.name and state[c].astype(str).str.upper().eq("MT").any():
   state=state[state[c].astype(str).str.upper().eq("MT")]; break
 return state.to_crs(4674).dissolve()[[state.geometry.name]]

def sample_geometry(path, target_crs, limit=5000):
 path=Path(path)
 if not path.exists(): return gpd.GeoDataFrame(geometry=[],crs=target_crs)
 pf=pq.ParquetFile(path); md=json.loads((pf.schema_arrow.metadata or {}).get(b"geo",b"{}").decode())
 primary=md.get("primary_column","geometry"); crs=md.get("columns",{}).get(primary,{}).get("crs")
 if primary not in pf.schema_arrow.names: return gpd.GeoDataFrame(geometry=[],crs=target_crs)
 per=max(1,math.ceil(limit/max(pf.num_row_groups,1))); values=[]
 for group in range(pf.num_row_groups):
  vals=pf.read_row_group(group,columns=[primary]).column(0).drop_null().to_pylist()
  if vals: values.extend(vals[::max(1,len(vals)//per)][:per])
 frame=gpd.GeoDataFrame(geometry=shapely.from_wkb(values[:limit]) if values else [],crs=crs or target_crs)
 frame=frame[frame.geometry.notna()&~frame.geometry.is_empty]
 return frame.to_crs(target_crs) if not frame.empty and frame.crs!=target_crs else frame

def plot_radam(ax, path, target_crs):
 """Show the corrected RADAM intersection by forest/cerrado class."""
 try:
  # The validated full-coverage product is intentionally tabular. Its spatial
  # source is the correct proxy-universe RADAM intersection used by all three
  # branches, retained here for a truthful cartographic preview.
  source=ROOT/"data/raw/simcar_proxy/SIMCAR_P_vegetacao_radambrasil_x_car_atp.parquet"
  radam=gpd.read_parquet(source,columns=["FITOECOLOG","geometry"])
  if radam.crs!=target_crs: radam=radam.to_crs(target_crs)
  colors=radam["FITOECOLOG"].astype(str).str.upper().map({"FLORESTA":"#356B58","CERRADO":"#D39A3A"}).fillna("#9A8F78")
  radam.plot(ax=ax,color=colors,edgecolor="none",alpha=.9)
  return True
 except (KeyError,ValueError):
  return False

def write_outputs(audit):
 QA.mkdir(parents=True,exist_ok=True); FIG.mkdir(parents=True,exist_ok=True)
 audit.to_csv(QA/f"spatial_input_coverage_audit_{DATE}.csv",index=False)
 lines=["# Spatial input coverage audit","",f"- Inputs/intersections audited: {len(audit)}",f"- Failed exhaustive inputs: {(audit.audit_status.str.startswith('FAIL')).sum()}",""]
 (QA/f"spatial_input_coverage_audit_{DATE}.md").write_text("\n".join(lines),encoding="utf-8")
 show=audit.copy(); show["map_key"]=show.layer.map(map_key)
 show["universe_label"]=show.source_universe.map({"car_validated":"validado","car_digital":"digital","car_proxy":"proxy"})
 universes=show.groupby("map_key").universe_label.agg(lambda s:", ".join(dict.fromkeys(s)))
 show["preferred"]=show.path.astype(str).str.contains("full_coverage",case=False).astype(int)
 show=(show.sort_values(["map_key","preferred","pct_match"],ascending=[True,False,False]).drop_duplicates("map_key"))
 show["universes"]=show.map_key.map(universes); show=show.sort_values("map_key").reset_index(drop=True)
 boundary=state_boundary(); panels=math.ceil(len(show)/MAPS_PER_PANEL); outputs=[]
 for panel in range(panels):
  chunk=show.iloc[panel*MAPS_PER_PANEL:(panel+1)*MAPS_PER_PANEL]
  fig,axes=plt.subplots(2,2,figsize=(8.3,8.3),facecolor="white")
  for ax,row in zip(axes.flat,chunk.itertuples()):
   boundary.plot(ax=ax,facecolor="#F2F1EC",edgecolor="#777770",linewidth=.35)
   if row.map_key!="radam" or not plot_radam(ax,row.path,boundary.crs):
    geom=sample_geometry(row.path,boundary.crs)
    if not geom.empty:
     kinds=set(geom.geom_type.astype(str))
     if any("Point" in kind for kind in kinds): geom.plot(ax=ax,color="#343B3F",markersize=2.2,alpha=.95)
     elif any("Line" in kind for kind in kinds): geom.plot(ax=ax,color="#343B3F",linewidth=.9,alpha=.95)
     else: geom.plot(ax=ax,color="#4F585D",edgecolor="#30363A",linewidth=.12,alpha=.95)
    else: ax.text(.5,.5,"No intersecting features",transform=ax.transAxes,ha="center",va="center",fontsize=12,color="#6F787D")
   title="\n".join(textwrap.wrap(NAMES.get(row.map_key,row.map_key.replace("_"," ").title()),width=30))
   universe="\n".join(textwrap.wrap(f"SIMCAR universe: {row.universes.replace('validado','validated')}",width=35))
   ax.set_title(title,fontsize=12,fontweight="bold",loc="left",pad=3)
   ax.text(0,-.03,universe,transform=ax.transAxes,fontsize=12,color="#5B5B57",va="top"); ax.set_axis_off()
  for ax in axes.flat[len(chunk):]: ax.set_axis_off()
  fig.text(.055,.012,f"Panel {panel+1} of {panels}. Gray: intersection geometry. RADAM: forest (green) and Cerrado (ochre). Outline: Mato Grosso.",fontsize=12,color="#5B5B57")
  fig.subplots_adjust(left=.06,right=.985,top=.985,bottom=.08,hspace=.34,wspace=.12)
  out=FIG/f"Figure_16_spatial_inputs_panel_{panel+1:02d}_of_{panels:02d}.png"; fig.savefig(out,dpi=300,facecolor="white",bbox_inches="tight",pad_inches=.08); plt.close(fig); outputs.append(out)
 return outputs

def main():
 audit=load_inventory(); outputs=write_outputs(audit); failures=audit[audit.audit_status.str.startswith("FAIL")]
 print(f"Audited {len(audit)} inputs/intersections; unique maps={audit.layer.map(map_key).nunique()}; panels={len(outputs)}; failures={len(failures)}")
 if not failures.empty: raise SystemExit(failures[["source_universe","layer","pct_match","audit_status"]].to_string(index=False))
if __name__=="__main__": main()
