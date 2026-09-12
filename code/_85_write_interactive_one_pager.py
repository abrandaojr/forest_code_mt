from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import pandas as pd

import _00_paths as paths
from _80_write_one_pager import add_lr_without_2000_rule


paths.set_env()

ROOT = paths.ROOT
TABLES = paths.TABLES
REPORTS = paths.REPORTS
TODAY = paths.RUN_DATE
OUT = REPORTS / f"forest_code_mt_interactive_one_pager_{TODAY}.html"


def n(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def active_fc() -> pd.DataFrame:
    fc = pd.read_parquet(TABLES / f"forest_code_mt_priority_consolidated_{TODAY}.parquet")
    status = fc["SITUACAO"].astype(str).str.upper()
    fc = fc.loc[~status.str.contains("CANCELADO|INDEFERIDO|REJEIT", na=False)].copy()
    fc["mun_code"] = fc["mun_geocodigo"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    return add_lr_without_2000_rule(fc[fc["mun_code"].str.startswith("51")].copy())


def overview(fc: pd.DataFrame) -> dict[str, object]:
    gta = pd.read_parquet(TABLES / f"forest_code_gta_final_mt_{TODAY}.parquet")
    direct = n(gta["slaughter_or_export_cattle"]).gt(0)
    gt50 = gta["direct_slaughter_gt50"].fillna(False).astype(bool)
    total = n(fc["calc_deficit_total_ha"])
    app = n(fc["app_restore_ha"])
    lr = n(fc["rl_adj_deficit_ha"])
    restore = n(fc["rl_restore_ha"]) + app
    compensate = n(fc["rl_compensate_ha"])
    no2000 = n(fc["rl_adj_deficit_without_cons2000_ha"]) + app
    secondary = pd.read_parquet(TABLES / f"forest_code_mt_priority_consolidated_with_secondary_{TODAY}.parquet")
    return {
        "properties": int(len(fc)),
        "area": float(n(fc["area_ha_car"]).sum()),
        "affected_properties": int(total.gt(0).sum()),
        "affected_area": float(total.sum()),
        "lr_properties": int(lr.gt(0).sum()),
        "lr_area": float(lr.sum()),
        "app_properties": int(app.gt(0).sum()),
        "app_area": float(app.sum()),
        "restore_area": float(restore.sum()),
        "compensate_area": float(compensate.sum()),
        "without_2000_properties": int(no2000.gt(0).sum()),
        "without_2000_area": float(no2000.sum()),
        "secondary_area": float(n(secondary["secondary_vegetation_ha"]).sum()),
        "direct_properties": int(direct.sum()),
        "direct_area": float(n(gta.loc[direct, "area_ha_car"]).sum()),
        "direct_gt50_properties": int(gt50.sum()),
        "direct_gt50_area": float(n(gta.loc[gt50, "area_ha_car"]).sum()),
    }


def html(data: dict[str, object]) -> str:
    payload = json.dumps({"metrics": data}, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0f172a">
<meta name="description" content="Vertical mobile carousel with Forest Code diagnostic results for Mato Grosso.">
<meta property="og:title" content="Forest Code Diagnostic | Mato Grosso">
<meta property="og:description" content="Light vertical summary for mobile and WhatsApp sharing.">
<title>Forest Code Diagnostic | Mato Grosso</title>
<style>
:root {{ --ink:#101827; --muted:#5d6675; --line:#d9e0ea; --bg:#f5f7fb; --panel:#fff; --blue:#1d4ed8; }}
* {{ box-sizing:border-box; }}
html {{ width:100%; height:100%; -webkit-text-size-adjust:100%; scroll-snap-type:y mandatory; }}
body {{ margin:0; width:100%; min-height:100%; overflow-x:hidden; font-family:Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; color:var(--ink); background:var(--bg); }}
header {{ position:fixed; top:0; left:0; right:0; z-index:5; padding:calc(10px + env(safe-area-inset-top)) 12px 10px; background:#0f172a; color:white; border-bottom:1px solid #273449; }}
.top {{ display:flex; gap:8px; align-items:center; justify-content:space-between; max-width:760px; margin:auto; }}
h1 {{ margin:0; font-size:16px; line-height:1.15; letter-spacing:0; }}
.actions {{ display:flex; gap:7px; }}
button {{ border:1px solid var(--line); background:white; color:var(--ink); border-radius:8px; padding:8px 10px; min-height:40px; font-weight:800; font-size:13px; -webkit-appearance:none; appearance:none; }}
main {{ padding-top:64px; }}
.slide {{ min-height:calc(100svh - 64px); scroll-snap-align:start; padding:18px 14px; display:flex; align-items:center; justify-content:center; }}
.panel {{ width:min(100%,430px); min-height:min(680px,calc(100svh - 104px)); background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:18px; display:flex; flex-direction:column; justify-content:space-between; }}
.eyebrow {{ font-size:12px; color:var(--muted); text-transform:uppercase; font-weight:900; line-height:1.25; }}
.tag {{ display:inline-block; width:max-content; padding:7px 9px; border-radius:999px; font-size:12px; font-weight:900; background:#eef2ff; color:#1e3a8a; }}
.title {{ font-size:30px; line-height:1.05; font-weight:950; margin:10px 0 12px; letter-spacing:0; }}
.text {{ font-size:16px; line-height:1.38; color:#334155; margin:0; }}
.kpis {{ display:grid; gap:12px; margin-top:18px; }}
.kpi {{ border-top:1px solid var(--line); padding-top:12px; }}
.value {{ font-size:35px; line-height:1; font-weight:950; }}
.unit {{ color:var(--muted); font-size:13px; margin-top:5px; }}
.bar {{ height:10px; background:#e5eaf2; border-radius:999px; overflow:hidden; margin-top:12px; }}
.fill {{ height:100%; background:var(--blue); }}
footer {{ padding:12px 14px calc(16px + env(safe-area-inset-bottom)); color:var(--muted); font-size:12px; text-align:center; scroll-snap-align:end; }}
@media (min-width:780px) {{ main {{ max-width:760px; margin:auto; }} .panel {{ min-height:520px; }} }}
</style>
</head>
<body>
<header>
  <div class="top">
    <h1 data-i18n="title">Forest Code Diagnostic</h1>
    <div class="actions">
      <button id="lang">Português</button>
      <button id="share" data-i18n="share">Share</button>
    </div>
  </div>
</header>
<main id="slides"></main>
<footer data-i18n="footer">Source: Forest Code model outputs. Values use hectares and property counts.</footer>
<script>
var DATA = {payload};
var lang = 'en';
var T = {{
  en: {{
    title:'Forest Code Diagnostic', share:'Share', footer:'Source: Forest Code model outputs. Values use hectares and property counts.',
    units:['properties','hectares','hectares','hectares','hectares','hectares','hectares','hectares','properties',''],
    slides:[
      ['Mato Grosso','Property-level Forest Code compliance, summarized for mobile reading.','Properties analyzed','Area analyzed'],
      ['Source hierarchy','Each property uses the best available CAR source: validated first, digital second, proxy third.','Properties','Area'],
      ['Overall non-compliance','Liabilities are calculated by property before aggregation.','Non-compliant properties','Total non-compliance'],
      ['APP','Permanent Preservation Area deficits requiring restoration.','Non-compliant APP properties','APP non-compliance'],
      ['Legal Reserve','Adjusted Legal Reserve deficit after Forest Code rules.','LR non-compliant properties','LR non-compliance'],
      ['Regularization','Liability is separated into restoration on farm and compensation off farm.','Restore on farm','Compensate off farm'],
      ['2000 rule scenario','Legal Reserve results change when the 2000 rule is removed.','Non-compliance without 2000 rule','Affected area'],
      ['Secondary vegetation','Secondary vegetation is a sensitivity layer, not a replacement for core rules.','Secondary vegetation','Scenario area'],
      ['Supply chain','Direct suppliers have any slaughter/export outflow. A second flag marks >50% of outflow.','Direct suppliers','Direct >50% outflow'],
      ['Reading note','This compact page is for public sharing. The manuscript and tables keep the full method.','Final report','Mobile carousel']
    ]
  }},
  pt: {{
    title:'Diagnóstico do Código Florestal', share:'Compartilhar', footer:'Fonte: resultados do modelo do Código Florestal. Valores em hectares e número de propriedades.',
    units:['propriedades','hectares','hectares','hectares','hectares','hectares','hectares','hectares','propriedades',''],
    slides:[
      ['Mato Grosso','Conformidade com o Código Florestal por propriedade, resumida para celular.','Propriedades analisadas','Área analisada'],
      ['Hierarquia das fontes','Cada propriedade usa a melhor fonte CAR disponível: validado, digital e proxy.','Propriedades','Área'],
      ['Não conformidade total','Os passivos são calculados por propriedade antes da agregação.','Propriedades não conformes','Não conformidade total'],
      ['APP','Déficits em Área de Preservação Permanente que exigem restauração.','Propriedades com APP não conforme','Não conformidade em APP'],
      ['Reserva Legal','Déficit ajustado de Reserva Legal após as regras do Código Florestal.','Propriedades com RL não conforme','Não conformidade em RL'],
      ['Regularização','O passivo é separado entre restaurar na fazenda e compensar fora da fazenda.','Restaurar na fazenda','Compensar fora da fazenda'],
      ['Regra de 2000','A Reserva Legal muda quando a regra de 2000 é removida.','Não conformidade sem regra de 2000','Área afetada'],
      ['Vegetação secundária','A vegetação secundária é uma sensibilidade, não substitui as regras centrais.','Vegetação secundária','Área do cenário'],
      ['Cadeia de fornecedores','Fornecedor direto tem qualquer saída para abate/exportação. Outro indicador marca >50% da saída.','Fornecedores diretos','Diretos >50% da saída'],
      ['Nota de leitura','Esta página compacta é para compartilhamento público. O manuscrito e as tabelas mantêm o método completo.','Relatório final','Carrossel móvel']
    ]
  }}
}};
function fmt(v,d) {{ d=d||0; return isNaN(v) ? v : Number(v||0).toLocaleString('en-US',{{maximumFractionDigits:d,minimumFractionDigits:d}}); }}
function values() {{
  var m=DATA.metrics;
  return [[m.properties,m.area],[m.properties,m.area],[m.affected_properties,m.affected_area],[m.app_properties,m.app_area],[m.lr_properties,m.lr_area],[m.restore_area,m.compensate_area],[m.without_2000_properties,m.without_2000_area],[m.secondary_area,m.secondary_area],[m.direct_properties,m.direct_gt50_properties],['DOCX','HTML']];
}}
function renderText() {{
  document.documentElement.lang=lang;
  var nodes=document.querySelectorAll('[data-i18n]');
  for(var i=0;i<nodes.length;i++) nodes[i].textContent=T[lang][nodes[i].getAttribute('data-i18n')];
  document.getElementById('lang').textContent=lang==='en'?'Português':'English';
}}
function renderSlides() {{
  var slides=T[lang].slides, vals=values(), html='';
  for(var i=0;i<slides.length;i++) {{
    var s=slides[i], v=vals[i], unit=T[lang].units[i] || '';
    html += '<section class="slide"><article class="panel"><div><span class="tag">'+(i+1)+' / '+slides.length+'</span><div class="eyebrow">Forest Code</div><div class="title">'+s[0]+'</div><p class="text">'+s[1]+'</p></div><div class="kpis">';
    html += '<div class="kpi"><div class="eyebrow">'+s[2]+'</div><div class="value">'+fmt(v[0])+'</div><div class="unit">'+unit+'</div></div>';
    html += '<div class="kpi"><div class="eyebrow">'+s[3]+'</div><div class="value">'+fmt(v[1])+'</div><div class="unit">'+unit+'</div></div>';
    html += '<div class="bar"><div class="fill" style="width:'+Math.max(10,Math.min(100,(i+1)*10))+'%"></div></div></div></article></section>';
  }}
  document.getElementById('slides').innerHTML=html;
}}
function render() {{ renderText(); renderSlides(); }}
document.getElementById('lang').addEventListener('click', function(){{ lang=lang==='en'?'pt':'en'; render(); }});
document.getElementById('share').addEventListener('click', function(){{ var text=T[lang].title+' - Mato Grosso'; if(navigator.share) {{ navigator.share({{title:T[lang].title,text:text,url:location.href}}).catch(function(){{ location.href='https://wa.me/?text='+encodeURIComponent(text+' '+location.href); }}); }} else {{ location.href='https://wa.me/?text='+encodeURIComponent(text+' '+location.href); }} }});
render();
</script>
</body>
</html>"""


def main() -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html(overview(active_fc())), encoding="utf-8")
    print(OUT)
    return OUT


if __name__ == "__main__":
    main()

