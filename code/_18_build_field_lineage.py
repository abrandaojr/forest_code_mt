from __future__ import annotations

import ast
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
DATE = "20260818"
DOC_DATE = "20260930"
OUT = ROOT / "deliverables" / "06_documentation"
PRE = ROOT / "data" / "pre"
TABLES = ROOT / "out" / "table"

SOURCES = {
    "simcar_validado": PRE / "car_validated" / f"car_atp_joined_{DATE}.parquet",
    "simcar_digital": PRE / "car_digital" / f"car_atp_joined_{DATE}.parquet",
    "simcar_proxy": PRE / "car_proxy" / f"car_atp_joined_{DATE}.parquet",
}
FINAL_OUTPUTS = {
    "property_baseline": TABLES / f"forest_code_mt_priority_consolidated_{DATE}.parquet",
    "property_secondary": TABLES / f"forest_code_mt_priority_consolidated_with_secondary_{DATE}.parquet",
    "property_csv": TABLES / f"forest_code_mt_priority_consolidated_with_secondary_{DATE}.csv",
    "cattle_baseline": TABLES / f"forest_code_gta_final_mt_{DATE}.parquet",
    "cattle_secondary": TABLES / f"forest_code_gta_final_mt_with_secondary_{DATE}.parquet",
}


def schema(path: Path) -> list[str]:
    return pq.ParquetFile(path).schema_arrow.names if path.exists() else []


def load_assignment_list(path: Path, name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return list(ast.literal_eval(node.value))
    return []


def load_mapping(path: Path, name: str) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return dict(ast.literal_eval(node.value))
    return {}


def formula_assignments(path: Path, function_names: set[str]) -> dict[str, dict[str, object]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, object]] = {}
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in function_names]:
        for node in ast.walk(fn):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id in {"df", "out", "work"}
                and isinstance(target.slice, ast.Constant)
                and isinstance(target.slice.value, str)
            ):
                continue
            field = target.slice.value
            expr = ast.unparse(node.value)
            deps: set[str] = set()
            for sub in ast.walk(node.value):
                if (
                    isinstance(sub, ast.Subscript)
                    and isinstance(sub.value, ast.Name)
                    and sub.value.id in {"df", "out", "work"}
                    and isinstance(sub.slice, ast.Constant)
                    and isinstance(sub.slice.value, str)
                ):
                    deps.add(sub.slice.value)
                if isinstance(sub, ast.Call) and sub.args:
                    call_name = getattr(sub.func, "id", None) or getattr(sub.func, "attr", None)
                    if call_name in {"col_or_zero", "num", "raw"}:
                        for arg in sub.args:
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                deps.add(arg.value)
            deps.discard(field)
            result[field] = {
                "expression": expr,
                "dependencies": sorted(deps),
                "script": str(path.relative_to(ROOT)).replace("\\", "/"),
                "function": fn.name,
                "line": node.lineno,
            }
    return result


def add_node(nodes: dict[str, dict], node_id: str, **attrs) -> None:
    if node_id not in nodes:
        nodes[node_id] = {"id": node_id, **attrs}
    else:
        nodes[node_id].update({k: v for k, v in attrs.items() if v not in (None, "", [])})


def build_lineage() -> dict[str, object]:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    final_schemas = {name: schema(path) for name, path in FINAL_OUTPUTS.items() if path.suffix == ".parquet"}
    final_union = set().union(*(set(v) for v in final_schemas.values())) if final_schemas else set()
    metric_cols = set(load_assignment_list(ROOT / "code" / "_20_build_priority.py", "METRIC_COLS"))

    source_maps = {
        "simcar_validado": load_mapping(ROOT / "code" / "preprocess" / "_12_preprocess_validated.py", "LAYER_NAME_MAP"),
        "simcar_digital": load_mapping(ROOT / "code" / "preprocess" / "_11_preprocess_digital.py", "LAYER_NAME_MAP"),
        "simcar_proxy": {},
    }

    formulae = {}
    for path, functions in [
        (ROOT / "code" / "_11_forest_code_compliance.py", {"compute_forest_code_metrics", "add_secondary_vegetation_scenarios", "add_cons2000_scenarios"}),
        (ROOT / "code" / "_20_build_priority.py", {"normalize_source"}),
        (ROOT / "code" / "_30_build_gta.py", {"build_final_workbook"}),
    ]:
        formulae.update(formula_assignments(path, functions))

    for source, path in SOURCES.items():
        source_id = f"source:{source}"
        add_node(nodes, source_id, label=source, type="source", path=str(path.relative_to(ROOT)).replace("\\", "/"))
        mapped_values = set(source_maps[source].values())
        for field in schema(path):
            field_id = f"field:{field}"
            add_node(
                nodes,
                field_id,
                label=field,
                type="field",
                in_final=field in final_union,
                selected_metric=field in metric_cols,
                calculated=field in formulae,
            )
            edges.append({"from": source_id, "to": field_id, "type": "provides", "source": source})
        for raw_name, canonical in source_maps[source].items():
            raw_id = f"raw:{source}:{raw_name}"
            add_node(nodes, raw_id, label=raw_name, type="raw_layer", source=source)
            canonical_id = f"field:{canonical}"
            add_node(nodes, canonical_id, label=canonical, type="field", in_final=canonical in final_union, selected_metric=canonical in metric_cols)
            edges.append({"from": raw_id, "to": canonical_id, "type": "renamed_to", "source": source})

    for field, meta in formulae.items():
        field_id = f"field:{field}"
        add_node(nodes, field_id, label=field, type="formula", in_final=field in final_union, calculated=True, formula=meta)
        for dep in meta["dependencies"]:
            dep_id = f"field:{dep}"
            add_node(nodes, dep_id, label=dep, type="field", in_final=dep in final_union, selected_metric=dep in metric_cols)
            edges.append({"from": dep_id, "to": field_id, "type": "used_by", "formula": meta["expression"]})

    for output, path in FINAL_OUTPUTS.items():
        output_id = f"output:{output}"
        add_node(nodes, output_id, label=output, type="output", path=str(path.relative_to(ROOT)).replace("\\", "/"), exists=path.exists())
        cols = final_schemas.get(output, [])
        for field in cols:
            field_id = f"field:{field}"
            add_node(nodes, field_id, label=field, type=nodes.get(field_id, {}).get("type", "field"), in_final=True)
            edges.append({"from": field_id, "to": output_id, "type": "exported_to"})

    orphan_final = sorted(f for f in final_union if f not in formulae and not any(f in schema(p) for p in SOURCES.values()))
    source_union = set().union(*(set(schema(p)) for p in SOURCES.values()))
    omitted_source_fields = sorted(source_union - final_union)
    used_fields = set(formulae)
    for meta in formulae.values():
        used_fields.update(meta["dependencies"])
    used_but_missing = sorted(used_fields - final_union)

    return {
        "metadata": {
            "title": "Mato Grosso Forest Code — complete field lineage",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "model_date": DATE,
            "scope": "SIMCAR validated, digital and proxy inputs; Python formulas; property and cattle outputs",
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
        "summary": {
            "source_field_count": len(source_union),
            "final_field_count": len(final_union),
            "calculated_field_count": len(formulae),
            "metric_export_list_count": len(metric_cols),
            "omitted_source_fields_count": len(omitted_source_fields),
            "used_but_missing_final": used_but_missing,
            "final_fields_without_source_or_formula": orphan_final,
        },
        "sources": {k: {"path": str(v.relative_to(ROOT)).replace("\\", "/"), "columns": schema(v)} for k, v in SOURCES.items()},
        "outputs": {k: {"path": str(v.relative_to(ROOT)).replace("\\", "/"), "exists": v.exists(), "columns": final_schemas.get(k, [])} for k, v in FINAL_OUTPUTS.items()},
        "formulas": formulae,
        "source_mappings": source_maps,
        "metric_export_fields": sorted(metric_cols),
        "omitted_source_fields": omitted_source_fields,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def html_document(data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forest Code — complete field lineage</title>
<style>
:root{{--bg:#f5f7fa;--panel:#fff;--ink:#16212c;--muted:#667788;--line:#c7d0d9;--source:#2457a7;--raw:#6b7280;--field:#c58a10;--formula:#c94f3d;--output:#3a7d44;--warn:#8a3ffc}}
*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--ink)}}
header{{padding:18px 24px;background:#17324d;color:white;display:flex;gap:18px;align-items:center;flex-wrap:wrap}}header h1{{font-size:20px;margin:0}}header p{{margin:0;color:#dbe7f3;font-size:13px}}
.layout{{display:grid;grid-template-columns:330px 1fr;height:calc(100vh - 76px)}}aside{{background:var(--panel);border-right:1px solid #dbe1e7;padding:16px;overflow:auto}}main{{position:relative;overflow:hidden}}
input,select{{width:100%;padding:9px 10px;margin:5px 0 10px;border:1px solid #c8d1da;border-radius:6px;background:white}}button{{padding:8px 10px;border:1px solid #b6c1cc;border-radius:6px;background:white;cursor:pointer;margin:3px}}
.stats{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0}}.stat{{background:#eef3f7;padding:8px;border-radius:6px}}.stat b{{display:block;font-size:18px}}.legend{{font-size:12px;line-height:1.8}}.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}}
#canvas{{width:100%;height:100%;display:block;background:radial-gradient(circle at center,#fff 0,#f5f7fa 72%)}}#tip{{position:absolute;display:none;pointer-events:none;background:#17212b;color:white;padding:8px 10px;border-radius:5px;font-size:12px;max-width:360px;z-index:4}}
#details{{font-size:12px;white-space:pre-wrap;background:#f7f9fb;border:1px solid #dbe1e7;border-radius:6px;padding:10px;max-height:300px;overflow:auto}}.warn{{color:#8a3ffc;font-weight:700}}
@media(max-width:800px){{.layout{{grid-template-columns:1fr;grid-template-rows:340px 1fr}}aside{{border-right:0;border-bottom:1px solid #ddd}}}}
</style></head><body>
<header><div><h1>Complete field-use map — Mato Grosso Forest Code</h1><p>Sources → fields → formulas → final files. Select a node to inspect its formula, origin, and destinations.</p></div></header>
<div class="layout"><aside>
<label>Search fields</label><input id="search" placeholder="e.g., cons_area_2008 or rl_restore_ha">
<label>Aggregation level</label><select id="filter"><option value="executive">Level 1 — Final results</option><option value="overview">Level 2 — Core logic</option><option value="final">Level 3 — Exported fields</option><option value="formulas">Level 4 — Calculations</option><option value="used">Level 5 — Used fields</option><option value="all">Level 6 — Complete inventory</option><option value="omitted">Audit — Not exported</option></select>
<label>Theme</label><select id="theme"><option value="all">All themes</option><option value="lr">Legal Reserve</option><option value="app">Permanent Preservation Area</option><option value="secondary">Secondary vegetation</option><option value="cattle">Cattle supply chain</option><option value="identity">Property identity</option><option value="other">Other calculations</option></select>
<div><button id="reset">Reset</button><button id="fit">Center network</button></div>
<div class="stats"><div class="stat"><b id="nNodes"></b>nodes</div><div class="stat"><b id="nEdges"></b>links</div><div class="stat"><b id="nFormula"></b>formulas</div><div class="stat"><b id="nOmitted"></b>not exported</div></div>
<div class="legend"><b>Metro routes</b><div><span class="dot" style="background:#1f67b1"></span>Legal Reserve</div><div><span class="dot" style="background:#e17b25"></span>Permanent Preservation Area</div><div><span class="dot" style="background:#3a8f5b"></span>Secondary vegetation</div><div><span class="dot" style="background:#7a4ca5"></span>Cattle supply chain</div><div><span class="dot" style="background:#667788"></span>Property identity</div><div><span class="dot" style="background:#c19a32"></span>Other calculations</div><div>Double-ring station = interchange</div></div>
<h3>Details</h3><div id="details">Select a node.</div>
</aside><main><canvas id="canvas"></canvas><div id="tip"></div></main></div>
<script id="lineage-data" type="application/json">{payload}</script>
<script>
const data=JSON.parse(document.getElementById('lineage-data').textContent), canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d');
const colors={{source:'#2457a7',raw_layer:'#6b7280',field:'#c58a10',formula:'#c94f3d',output:'#3a7d44',omitted:'#8a3ffc'}};
const routeColors={{lr:'#1f67b1',app:'#e17b25',secondary:'#3a8f5b',cattle:'#7a4ca5',identity:'#667788',other:'#c19a32'}};
const omitted=new Set(data.omitted_source_fields);
const overviewFields=new Set(['cons_area_2008','rl_req_total_ha','rl_exist_total_ha','rl_restore_ha','rl_compensate_ha','app_restore_ha','secondary_vegetation_ha','rl_restore_with_secondary_ha','app_restore_with_secondary_ha','calc_deficit_total_ha','calc_gross_deficit_total_ha','property_baseline','property_secondary','property_csv']);
const executiveFields=new Set(['rl_restore_ha','rl_compensate_ha','app_restore_ha','rl_restore_with_secondary_ha','app_restore_with_secondary_ha','calc_deficit_total_ha','property_baseline','property_secondary','property_csv']);
function route(n){{const s=n.label.toLowerCase();if(s.includes('secondary')||s.includes('with_secondary'))return'secondary';if(s.startsWith('app')||s.includes('apprl'))return'app';if(s.startsWith('rl_')||s.includes('radam')||s.includes('cons_area')||s.includes('auas')||s.includes('nveg'))return'lr';if(s.includes('cattle')||s.includes('supplier')||s.includes('slaughter')||s.includes('t1_')||s.includes('t2_'))return'cattle';if(n.type==='source'||s.includes('property')||s.includes('car_')||s.includes('codigo'))return'identity';return'other'}}
function stage(n){{if(n.type==='source'||n.type==='raw_layer')return 0;if(n.type==='output')return 5;if(n.type==='formula')return n.label.includes('with_secondary')?4:3;if(n.selected_metric)return 2;return 1}}
const lanes={{identity:90,lr:270,app:510,secondary:730,cattle:920,other:1100}}, counts={{}};
const nodes=data.nodes.map(n=>{{const r=route(n),st=stage(n),key=r+'-'+st,i=counts[key]||0;counts[key]=i+1;return{{...n,route:r,x:100+st*260+(i%3)*62,y:lanes[r]+Math.floor(i/3)*34}}}}),byId=new Map(nodes.map(n=>[n.id,n]));
for(const n of nodes)n.routes=new Set([n.route]);
for(const e of data.edges){{const a=byId.get(e.from),b=byId.get(e.to);if(a&&b){{a.routes.add(b.route);b.routes.add(a.route)}}}}
let zoom=.72,panX=40,panY=20,drag=null,selected=null,visibleNodes=nodes,visibleEdges=data.edges;
function resize(){{const r=canvas.getBoundingClientRect(),d=devicePixelRatio||1;canvas.width=r.width*d;canvas.height=r.height*d;ctx.setTransform(d,0,0,d,0,0);}}addEventListener('resize',resize);resize();
function radius(n){{return n.type==='output'?9:n.type==='source'?8:n.type==='formula'?6:5}}
function color(n){{if(n.type==='field'&&omitted.has(n.label))return colors.omitted;return routeColors[n.route]||colors.field}}
function screen(n){{return {{x:n.x*zoom+panX,y:n.y*zoom+panY}}}}
function draw(){{ctx.clearRect(0,0,canvas.width,canvas.height);ctx.save();const level=document.getElementById('filter').value,simple=level==='executive'||level==='overview';for(const e of visibleEdges){{const a=byId.get(e.from),b=byId.get(e.to);if(!a?.show||!b?.show)continue;const A=screen(a),B=screen(b),m=(A.x+B.x)/2,stroke=routeColors[b.route]||'#8997a5';ctx.lineJoin='round';ctx.lineCap='round';ctx.beginPath();ctx.moveTo(A.x,A.y);ctx.lineTo(m,A.y);ctx.lineTo(m,B.y);ctx.lineTo(B.x,B.y);ctx.strokeStyle='rgba(255,255,255,.92)';ctx.lineWidth=6;ctx.stroke();ctx.strokeStyle=stroke;ctx.globalAlpha=e.type==='used_by'?.58:.35;ctx.lineWidth=e.type==='used_by'?3:2;ctx.stroke();ctx.globalAlpha=1}}for(const n of visibleNodes){{if(!n.show)continue;const p=screen(n),r=radius(n)*(selected===n?1.5:1);if(n.routes.size>1){{ctx.beginPath();ctx.arc(p.x,p.y,r+5,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();ctx.strokeStyle='#17212b';ctx.lineWidth=1.5;ctx.stroke()}}ctx.beginPath();ctx.arc(p.x,p.y,r+2,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();ctx.strokeStyle=color(n);ctx.lineWidth=n.type==='formula'?4:3;ctx.stroke();if(n.type==='source'||n.type==='output'){{ctx.beginPath();ctx.arc(p.x,p.y,r-2,0,Math.PI*2);ctx.fillStyle=color(n);ctx.fill()}}if(simple||selected===n||zoom>1.05){{ctx.fillStyle='#17212b';ctx.font=simple?'12px Segoe UI':'11px Segoe UI';ctx.fillText(n.label,p.x+r+5,p.y+4)}}}}ctx.restore();requestAnimationFrame(draw)}}draw();
function nearest(ev){{const r=canvas.getBoundingClientRect(),x=ev.clientX-r.left,y=ev.clientY-r.top;let best=null,bd=14;for(const n of visibleNodes){{if(!n.show)continue;const p=screen(n),d=Math.hypot(p.x-x,p.y-y);if(d<bd){{best=n;bd=d}}}}return best}}
canvas.onpointerdown=e=>{{drag=nearest(e);if(!drag){{drag={{pan:true,x:e.clientX,y:e.clientY,px:panX,py:panY}}}}canvas.setPointerCapture(e.pointerId)}};canvas.onpointermove=e=>{{if(!drag)return;if(drag.pan){{panX=drag.px+e.clientX-drag.x;panY=drag.py+e.clientY-drag.y}}else{{const r=canvas.getBoundingClientRect();drag.x=(e.clientX-r.left-panX)/zoom;drag.y=(e.clientY-r.top-panY)/zoom}}}};canvas.onpointerup=e=>drag=null;
canvas.onclick=e=>{{const n=nearest(e);if(!n)return;selected=n;const incoming=data.edges.filter(x=>x.to===n.id).map(x=>byId.get(x.from)?.label).filter(Boolean),outgoing=data.edges.filter(x=>x.from===n.id).map(x=>byId.get(x.to)?.label).filter(Boolean);document.getElementById('details').textContent=JSON.stringify({{field:n.label,type:n.type,present_in_final_files:n.in_final,selected_for_export:n.selected_metric,formula:n.formula,inputs:incoming,outputs:outgoing,path:n.path}},null,2)}};
canvas.onwheel=e=>{{e.preventDefault();zoom=Math.max(.15,Math.min(3,zoom*(e.deltaY<0?1.1:.9)))}};
function applyFilter(){{const q=document.getElementById('search').value.toLowerCase(),f=document.getElementById('filter').value,t=document.getElementById('theme').value;for(const n of nodes){{const match=!q||n.label.toLowerCase().includes(q),base=n.in_final||n.type==='source'||n.type==='output',calc=base||n.calculated||n.type==='formula',used=calc||data.edges.some(e=>(e.from===n.id||e.to===n.id)&&(e.type==='used_by'||e.type==='renamed_to'));const level=f==='executive'&&(executiveFields.has(n.label)||n.type==='source'||n.type==='output')||f==='overview'&&(overviewFields.has(n.label)||n.type==='source'||n.type==='output')||f==='final'&&base||f==='formulas'&&calc||f==='used'&&used||f==='all'||f==='omitted'&&omitted.has(n.label);const thematic=t==='all'||n.route===t||n.type==='source'||n.type==='output';n.show=(q?match:level)&&thematic}}const ids=new Set(nodes.filter(n=>n.show).map(n=>n.id));document.getElementById('nNodes').textContent=ids.size;document.getElementById('nEdges').textContent=data.edges.filter(e=>ids.has(e.from)&&ids.has(e.to)).length}}
document.getElementById('search').oninput=applyFilter;document.getElementById('filter').onchange=applyFilter;document.getElementById('theme').onchange=applyFilter;document.getElementById('reset').onclick=()=>{{document.getElementById('search').value='';document.getElementById('filter').value='executive';document.getElementById('theme').value='all';applyFilter()}};document.getElementById('fit').onclick=()=>{{zoom=.72;panX=40;panY=20}};
document.getElementById('nFormula').textContent=data.summary.calculated_field_count;document.getElementById('nOmitted').textContent=data.summary.omitted_source_fields_count;applyFilter();
</script></body></html>'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = build_lineage()
    json_path = OUT / f"forest_code_field_lineage_{DOC_DATE}.json"
    html_path = OUT / f"forest_code_field_lineage_{DOC_DATE}.html"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(html_document(data), encoding="utf-8")
    print(json.dumps({"html": str(html_path), "json": str(json_path), "summary": data["summary"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
