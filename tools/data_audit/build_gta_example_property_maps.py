"""Build satellite/vector-layer atlases for six GTA-linked compliance examples."""

from pathlib import Path
import json
import sys

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent))
import build_example_property_maps as base

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "deliverables" / "04_presentation" / "assets" / "gta_examples"
OUT.mkdir(parents=True, exist_ok=True)
TABLE = ROOT / "out" / "table" / "forest_code_gta_final_mt_with_secondary_20261007.parquet"

SELECTED = [
    ("validated_large", "MT-5107602-4838366C339B49D69077F3DC87A8074C"),
    ("validated_small", "MT-5106257-60F736EB772F4CF6A460A8D0BE0ADCBB"),
    ("digital_large", "MT-5107750-3D69A53C7D644B4098DE759BD0FE2AF1"),
    ("digital_small", "MT-5102603-D132829CFF784C919A4FA35C7A5F32A5"),
    ("proxy_large", "MT-5106828-23ABB407C9334E9F864BC6C07D00148C"),
    ("proxy_small", "MT-5103304-CDD5B177BF43405FA86B66729E82F424"),
]

METRIC_COLS = [
    "CODIGO_CAR", "car_join", "prop_id_unique", "input_file_type", "area_ha_car", "MODULOS_FI",
    "radam_forest_ha", "radam_cerrado_ha", "radam_forest_nveg24_ha", "radam_cerrado_nveg24_ha",
    "cons_area_2000", "cons_area_2008", "veg_2000_ha", "veg_2008_ha", "req_teto_art12_ha",
    "req_piso_art68_ha", "rl_req_base_ha", "rl_exist_total_ha", "auas_post2008", "rl_adj_deficit_ha",
    "rl_restore_ha", "rl_compensate_ha", "app_req_ha", "app_preserved_ha", "app_restore_ha",
    "avn_declared_ha", "appd_declared_ha", "app_fnl_cs08", "app_fnl_auas", "secondary_vegetation_ha",
    "calc_deficit_total_ha", "calc_deficit_total_with_secondary_ha", "supplier_type", "total_cattle_slaughter",
]


def metric_rows():
    df = pd.read_parquet(TABLE, columns=METRIC_COLS)
    df = df.drop_duplicates("CODIGO_CAR").set_index("CODIGO_CAR")
    return {label: df.loc[code].to_dict() | {"CODIGO_CAR": code, "label": label} for label, code in SELECTED}


def prop_for(row):
    if row["input_file_type"] == "simcar_validado":
        path, field, key = RAW / "simcar_validado" / "CAR_ATP.parquet", "CAR_FEDERA", row["CODIGO_CAR"]
    else:
        path, field, key = RAW / "simcar_requerido" / "CAR_ATP.parquet", "car_join", row["car_join"]
    table = pq.read_table(path, columns=[field, "geometry"], filters=[(field, "=", key)])
    gdf = gpd.GeoDataFrame.from_arrow(table).dissolve().reset_index(drop=True)
    return gdf


def validated_proxy_keys(row):
    car = pq.read_table(RAW / "simcar_requerido" / "CAR_ATP.parquet", columns=["CODIGO_CAR", "car_join"],
                        filters=[("CODIGO_CAR", "=", row["CODIGO_CAR"])]).to_pandas()
    keys = car["car_join"].dropna().astype(str).unique().tolist()
    rad = pq.read_table(RAW / "simcar_proxy" / "SIMCAR_P_vegetacao_radambrasil_x_car_atp.parquet",
                        columns=["car_join", "FITOECOLOG", "area_ha"], filters=[("car_join", "in", keys)]).to_pandas()
    piv = rad.pivot_table(index="car_join", columns="FITOECOLOG", values="area_ha", aggfunc="sum", fill_value=0)
    target = np.array([row["radam_forest_ha"], row["radam_cerrado_ha"]], dtype=float)
    best = min(keys, key=lambda k: np.abs(np.array([piv.loc[k].get("FLORESTA", 0), piv.loc[k].get("CERRADO", 0)]) - target).sum())
    cons = pq.read_table(RAW / "simcar_proxy" / "SIMCAR_P_cons_area_2000_net_max_x_car_atp.parquet",
                         columns=["car_join", "area_ha"], filters=[("car_join", "in", keys)]).to_pandas()
    cons_key = cons.groupby("car_join")["area_ha"].sum().idxmax()
    return best, cons_key


def geom(path, filters):
    return base.read_geometry(path, filters)


def layers_for(row, prop):
    proxy = RAW / "simcar_proxy"
    src = row["input_file_type"]
    if src == "simcar_validado":
        proxy_key, cons_key = validated_proxy_keys(row)
        f = [("prop_id_unique", "=", row["prop_id_unique"])]
        root = RAW / "simcar_validado"
        layers = {
            "radam": geom(proxy / "SIMCAR_P_vegetacao_radambrasil_x_car_atp.parquet", [("car_join", "=", proxy_key)]),
            "cons2000": geom(proxy / "SIMCAR_P_cons_area_2000_net_max_x_car_atp.parquet", [("car_join", "=", cons_key)]),
            "cons2008": geom(root / "SIMCAR_CAR_AREA_CONSOLIDADA_x_car_atp.parquet", f),
            "auas": geom(root / "CAR_AUAS_x_car_atp.parquet", f), "app": geom(root / "CAR_APP_x_car_atp.parquet", f),
            "avn": geom(root / "CAR_AVN_x_car_atp.parquet", f), "appd": geom(root / "CAR_APPD_x_car_atp.parquet", f),
            "app_auas": None,
        }
    else:
        key = row["car_join"]
        layers = {
            "radam": geom(proxy / "SIMCAR_P_vegetacao_radambrasil_x_car_atp.parquet", [("car_join", "=", key)]),
            "cons2000": geom(proxy / "SIMCAR_P_cons_area_2000_net_max_x_car_atp.parquet", [("car_join", "=", key)]),
        }
        if src == "simcar_digital":
            oid = int(str(key).split("_")[-1]); f = [("car_OBJECTID", "=", oid)]; root = RAW / "simcar_digital"
            layers |= {"cons2008": geom(root / "SIMCAR_D_AREA_CONSOLIDADA_x_car_atp.parquet", f), "auas": geom(root / "SIMCAR_D_AUAS_x_car_atp.parquet", f),
                       "app": geom(root / "SIMCAR_D_APP_x_car_atp.parquet", f), "avn": geom(root / "SIMCAR_D_AVN_x_car_atp.parquet", f),
                       "appd": geom(root / ("SIMCAR_D_APPD_4A10MF_AC_x_car_atp.parquet" if row["MODULOS_FI"] > 4 else "SIMCAR_D_APPD_2A4MF_AC_x_car_atp.parquet"), f),
                       "app_auas": geom(root / "SIMCAR_D_APPD_AUAS_x_car_atp.parquet", f)}
        else:
            layers |= {"cons2008": geom(proxy / "SIMCAR_P_cons_area_2008_net_max_x_car_atp.parquet", [("car_join", "=", key)]),
                       "auas": geom(proxy / "SIMCAR_P_auas_post2008_x_car_atp.parquet", [("car_join", "=", key)]),
                       "app": geom(proxy / "SIMCAR_P_app_x_car_atp_fnl.parquet", [("car_join", "=", key)]),
                       "avn": geom(proxy / "SIMCAR_P_app_fnl_avn24_x_car_atp_fnl.parquet", [("car_join", "=", key)]),
                       "appd": geom(proxy / "SIMCAR_P_app_fnl_cs08_x_car_atp_fnl.parquet", [("car_join", "=", key)]),
                       "app_auas": geom(proxy / "SIMCAR_P_app_fnl_auas_x_car_atp_fnl.parquet", [("car_join", "=", key)])}
    vegetation = gpd.read_file(proxy / "input_prodes_native_vegetation_2024_plus_sv.shp", bbox=tuple(prop.total_bounds))
    layers["native"] = vegetation[vegetation["layer"].astype(str).eq("input_prodes_native_vegetation_2024_TILED")].copy()
    layers["secondary"] = vegetation[vegetation["layer"].astype(str).eq("input_secondary_forest_dissolved")].copy()
    return {k: base.clip_to_property(v, prop) for k, v in layers.items()}


def make_map(row, prop, layers, suffix, panels):
    p3857 = prop.to_crs(3857); minx, miny, maxx, maxy = p3857.total_bounds
    span = max(maxx-minx, maxy-miny); pad = max(span*.18, 500)
    mosaic, extent = base.esri_mosaic((minx-pad,miny-pad,maxx+pad,maxy+pad), target_px=800)
    # Match the exported image aspect ratio to the slide region.  The earlier
    # 15 x 5 canvas left a large white band below long or narrow properties.
    # A single context map is near-square; multi-panel atlases are deliberately
    # shallow so the maps fill the presentation slide.
    figsize = (7.4, 6.0) if len(panels) == 1 else (15, 3.35 if len(panels) == 4 else 3.55)
    fig, axes = plt.subplots(1, len(panels), figsize=figsize, dpi=170)
    axes = np.atleast_1d(axes)
    for ax, (key, title, reported, color, cat) in zip(axes, panels):
        base.draw_layer_panel(ax, prop, layers.get(key), title, reported, color, mosaic, extent, cat)
    fig.text(.01,.012,"White/dark outline: CAR property boundary | Satellite: Esri World Imagery",fontsize=8,color="#5D716C")
    fig.tight_layout(rect=(0,.055,1,1),w_pad=.75)
    path = OUT / f"{row['label']}_{suffix}.png"; fig.savefig(path,bbox_inches="tight",pad_inches=.04,facecolor="white"); plt.close(fig)
    return str(path).replace("\\", "/")


def exclusive_app_partition(layers):
    """Partition APP into non-overlapping current-native, post-2008, and residual pre-2008 classes."""
    app = layers.get("app")
    if app is None or app.empty:
        return {"app_native": None, "app_post2008": None, "app_pre2008": None}, {"app": 0.0, "native": 0.0, "pre": 0.0, "post": 0.0}
    crs = app.crs
    app_geom = app.geometry.union_all()
    post_source = layers.get("auas")
    post_geom = app_geom.intersection(post_source.geometry.union_all()) if post_source is not None and not post_source.empty else app_geom.buffer(0).difference(app_geom)
    native_source = layers.get("native")
    native_geom = app_geom.intersection(native_source.geometry.union_all()) if native_source is not None and not native_source.empty else app_geom.buffer(0).difference(app_geom)
    # Recent clearing retains priority as a legal-history class. Any apparent
    # overlap is removed from current native vegetation before the residual is
    # assigned to the pre-2008 class.
    native_geom = native_geom.difference(post_geom)
    pre_geom = app_geom.difference(post_geom.union(native_geom))
    frames = {
        "app_native": gpd.GeoDataFrame(geometry=[native_geom], crs=crs) if not native_geom.is_empty else None,
        "app_post2008": gpd.GeoDataFrame(geometry=[post_geom], crs=crs) if not post_geom.is_empty else None,
        "app_pre2008": gpd.GeoDataFrame(geometry=[pre_geom], crs=crs) if not pre_geom.is_empty else None,
    }
    area = lambda geom: float(geom.area / 10000) if not geom.is_empty else 0.0
    values = {"app": area(app_geom), "native": area(native_geom), "pre": area(pre_geom), "post": area(post_geom)}
    values["closure_error"] = values["native"] + values["pre"] + values["post"] - values["app"]
    return frames, values


def main():
    rows = metric_rows(); manifest=[]
    for label, _ in SELECTED:
        r=rows[label]; prop=prop_for(r); layers=layers_for(r,prop)
        app_layers, app_values = exclusive_app_partition(layers)
        layers.update(app_layers)
        fmt=lambda v:f"{float(v or 0):,.2f} ha"
        r["satellite_map"] = make_map(r,prop,{"boundary":prop},"satellite",[("boundary","CAR property boundary",fmt(r["area_ha_car"]),"#9FC65B",False)])
        r["lr_map"] = make_map(r,prop,layers,"lr",[("radam","RADAM formation",f"Forest {fmt(r['radam_forest_ha'])} | Cerrado {fmt(r['radam_cerrado_ha'])}","#1E6B52",True),("native","Native vegetation in 2024",fmt(r['rl_exist_total_ha']),"#2E8B57",False),("secondary","Secondary vegetation",fmt(r['secondary_vegetation_ha']),"#9FC65B",False)])
        r["temporal_map"] = make_map(r,prop,layers,"temporal",[("cons2000","Cleared area by 2000",fmt(r['cons_area_2000']),"#B95B4C",False),("cons2008","Consolidated area by 2008",fmt(r['cons_area_2008']),"#D49A45",False),("auas","Post-2008 alternative land use",fmt(r['auas_post2008']),"#7A4CA5",False)])
        r["app_partition_total_ha"] = app_values["app"]
        r["app_partition_native_ha"] = app_values["native"]
        r["app_partition_pre2008_ha"] = app_values["pre"]
        r["app_partition_post2008_ha"] = app_values["post"]
        r["app_partition_closure_error_ha"] = app_values["closure_error"]
        r["app_map"] = make_map(r,prop,layers,"app",[("app","Permanent Preservation Area",fmt(app_values['app']),"#2F80ED",False),("app_native","Current native vegetation inside APP",fmt(app_values['native']),"#1E6B52",False),("app_pre2008","Residual pre-2008 class",fmt(app_values['pre']),"#D49A45",False),("app_post2008","Post-2008 clearing inside APP",fmt(app_values['post']),"#B95B4C",False)])
        clean={k:(None if pd.isna(v) else v.item() if hasattr(v,"item") else v) for k,v in r.items()}; manifest.append(clean)
        print(label,r["CODIGO_CAR"])
    (OUT / "gta_example_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")


if __name__ == "__main__": main()
