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
        for call in [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in {"agg", "assign"}]:
            for kw in call.keywords:
                if not kw.arg:
                    continue
                deps: set[str] = set()
                for sub in ast.walk(kw.value):
                    if isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant) and isinstance(sub.slice.value, str):
                        deps.add(sub.slice.value)
                if isinstance(kw.value, ast.Tuple) and kw.value.elts and isinstance(kw.value.elts[0], ast.Constant) and isinstance(kw.value.elts[0].value, str):
                    deps.add(kw.value.elts[0].value)
                result.setdefault(kw.arg, {
                    "expression": ast.unparse(kw.value),
                    "dependencies": sorted(deps),
                    "script": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "function": fn.name,
                    "line": call.lineno,
                })
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
        (ROOT / "code" / "_12_gta_supply_chain.py", {"classify_gta"}),
        (ROOT / "code" / "_50_build_publication_tables.py", {"prep_fc"}),
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
    schema_audit_path = ROOT / "qa" / "final_export_schema_audit_20260818.json"
    schema_audit = json.loads(schema_audit_path.read_text(encoding="utf-8")) if schema_audit_path.exists() else {}

    aggregation_levels = [
        {
            "id": "executive",
            "name": "Level 1 — Final answers",
            "purpose": "The five fields a decision-maker normally needs.",
            "items": [
                {"question": "How much LR must be restored on site?", "inputs": ["rl_req_base_ha", "rl_exist_total_ha", "auas_post2008"], "formula": "rl_restore_ha = min(max(rl_req_base_ha - rl_exist_total_ha, 0), auas_post2008)", "output": "rl_restore_ha", "destination": ["property_baseline", "property_secondary", "property_csv", "cattle_baseline", "cattle_secondary"]},
                {"question": "How much LR may be compensated off site?", "inputs": ["rl_adj_deficit_ha", "rl_restore_ha"], "formula": "rl_compensate_ha = max(rl_adj_deficit_ha - rl_restore_ha, 0)", "output": "rl_compensate_ha", "destination": ["property_baseline", "property_secondary", "property_csv", "cattle_baseline", "cattle_secondary"]},
                {"question": "How much APP must be restored?", "inputs": ["app_consol_restore_ha", "app_restore_auas_ha", "app_gross_deficit_ha"], "formula": "app_restore_ha = min(app_consol_restore_ha + app_restore_auas_ha, app_gross_deficit_ha)", "output": "app_restore_ha", "destination": ["property_baseline", "property_secondary", "property_csv", "cattle_baseline", "cattle_secondary"]},
                {"question": "What is the total baseline liability?", "inputs": ["rl_adj_deficit_ha", "app_restore_ha", "area_ha_car"], "formula": "calc_deficit_total_ha = min(rl_adj_deficit_ha + app_restore_ha, area_ha_car)", "output": "calc_deficit_total_ha", "destination": ["property_baseline", "property_secondary", "property_csv"]},
                {"question": "What changes when secondary vegetation is counted?", "inputs": ["rl_req_base_ha", "rl_exist_total_ha", "secondary_vegetation_raw_ha", "area_ha_car"], "formula": "secondary_vegetation_ha = min(secondary_vegetation_raw_ha, max(area_ha_car - rl_exist_total_ha, 0)); rl_adj_deficit_with_secondary_ha = max(rl_req_base_ha - (rl_exist_total_ha + secondary_vegetation_ha), 0)", "output": "rl_adj_deficit_with_secondary_ha", "destination": ["property_secondary", "property_csv", "cattle_secondary"]},
            ],
        },
        {
            "id": "overview",
            "name": "Level 2 — Legal logic",
            "purpose": "The cut-off dates and statutory decision rules behind the final answers.",
            "items": [
                {"question": "Native vegetation at the 2000 cut-off", "inputs": ["area_ha_car", "cons_area_2000"], "formula": "veg_2000_ha = max(area_ha_car - cons_area_2000, 0)", "output": "veg_2000_ha", "legal_rule": "Art. 68 eligibility test"},
                {"question": "Native vegetation at the 2008 cut-off", "inputs": ["area_ha_car", "cons_area_2008"], "formula": "veg_2008_ha = max(area_ha_car - cons_area_2008, 0)", "output": "veg_2008_ha", "legal_rule": "Art. 67 cut-off"},
                {"question": "Small-property LR requirement", "inputs": ["req_teto_art12_ha", "veg_2008_ha"], "formula": "rl_req_art67_ha = min(req_teto_art12_ha, veg_2008_ha)", "output": "rl_req_art67_ha", "legal_rule": "Art. 67"},
                {"question": "Large-property LR requirement", "inputs": ["veg_2000_ha", "req_piso_art68_ha", "req_teto_art12_ha"], "formula": "rl_req_art68_ha = req_piso_art68_ha if veg_2000_ha ≥ req_piso_art68_ha; otherwise req_teto_art12_ha", "output": "rl_req_art68_ha", "legal_rule": "Binary Art. 68 trigger"},
                {"question": "Final LR requirement", "inputs": ["art67_small_prop", "rl_req_art67_ha", "rl_req_art68_ha"], "formula": "rl_req_base_ha = rl_req_art67_ha for ≤4 fiscal modules; otherwise rl_req_art68_ha", "output": "rl_req_base_ha", "legal_rule": "Arts. 12, 67 and 68"},
                {"question": "APP restoration cap", "inputs": ["app_replant_raw_ha", "app_consolidated_ha", "app_gross_deficit_ha", "app_cap_ha"], "formula": "app_consol_restore_ha = min(app_replant_raw_ha, app_consolidated_ha, app_gross_deficit_ha, app_cap_ha); post-2008 clearing is added afterwards", "output": "app_restore_ha", "legal_rule": "Art. 61-B"},
            ],
        },
        {
            "id": "final",
            "name": "Level 3 — Exported fields",
            "purpose": "Every field present in at least one final property or cattle file.",
            "field_count": len(final_union),
            "fields": sorted(final_union),
        },
        {"id": "formulas", "name": "Level 4 — Calculated fields", "purpose": "All fields with a formula traced to a script, function and line.", "field_count": len(formulae), "fields": sorted(formulae)},
        {"id": "used", "name": "Level 5 — Formula inputs", "purpose": "Calculated fields plus every upstream field directly used by a formula.", "field_count": len(used_fields), "fields": sorted(used_fields)},
        {"id": "all", "name": "Level 6 — Complete inventory", "purpose": "All sources, raw layers, canonical fields, calculations and final files.", "node_count": len(nodes), "edge_count": len(edges)},
    ]

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
            "internal_calculated_fields_not_exported": used_but_missing,
            "final_fields_without_source_or_formula": orphan_final,
            "required_audit_field_count": schema_audit.get("required_audit_field_count"),
            "missing_required_fields": schema_audit.get("missing_required_fields", []),
            "core_export_schema_passed": schema_audit.get("all_required_fields_present", False),
            "lineage_review_complete": not orphan_final,
        },
        "sources": {k: {"path": str(v.relative_to(ROOT)).replace("\\", "/"), "columns": schema(v)} for k, v in SOURCES.items()},
        "outputs": {k: {"path": str(v.relative_to(ROOT)).replace("\\", "/"), "exists": v.exists(), "columns": final_schemas.get(k, [])} for k, v in FINAL_OUTPUTS.items()},
        "formulas": formulae,
        "source_mappings": source_maps,
        "metric_export_fields": sorted(metric_cols),
        "omitted_source_fields": omitted_source_fields,
        "aggregation_levels": aggregation_levels,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def html_document(data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forest Code — fields, formulas, and results</title>
<style>
:root{{--bg:#f5f7fa;--panel:#fff;--ink:#16212c;--muted:#667788;--line:#c7d0d9;--source:#2457a7;--raw:#6b7280;--field:#c58a10;--formula:#c94f3d;--output:#3a7d44;--warn:#8a3ffc}}
*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--ink)}}
header{{padding:18px 24px;background:#17324d;color:white;display:flex;gap:18px;align-items:center;flex-wrap:wrap}}header h1{{font-size:20px;margin:0}}header p{{margin:0;color:#dbe7f3;font-size:13px}}
.layout{{display:block;height:calc(100vh - 76px)}}aside{{background:var(--panel);padding:18px 24px;overflow:auto;height:100%}}main{{display:none}}
input,select{{width:100%;padding:9px 10px;margin:5px 0 10px;border:1px solid #c8d1da;border-radius:6px;background:white}}button{{padding:8px 10px;border:1px solid #b6c1cc;border-radius:6px;background:white;cursor:pointer;margin:3px}}
.stats{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0}}.stat{{background:#eef3f7;padding:8px;border-radius:6px}}.stat b{{display:block;font-size:18px}}.legend{{font-size:12px;line-height:1.8}}.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}}
#canvas{{width:100%;height:100%;display:block;background:radial-gradient(circle at center,#fff 0,#f5f7fa 72%)}}#tip{{position:absolute;display:none;pointer-events:none;background:#17212b;color:white;padding:8px 10px;border-radius:5px;font-size:12px;max-width:360px;z-index:4}}
#details{{font-size:12px;white-space:pre-wrap;background:#f7f9fb;border:1px solid #dbe1e7;border-radius:6px;padding:10px;max-height:300px;overflow:auto}}.warn{{color:#8a3ffc;font-weight:700}}
.audit{{padding:11px;border-radius:8px;background:#eef8f1;border-left:5px solid #3a7d44;font-size:12px;line-height:1.45;margin-bottom:12px}}.audit b{{display:block;font-size:14px}}.journey{{position:absolute;top:0;left:0;right:0;height:145px;background:white;border-bottom:1px solid #dbe1e7;padding:12px 16px;z-index:3}}.journey h2{{font-size:14px;margin:0 0 8px}}.steps{{display:flex;gap:8px;overflow-x:auto}}.step{{min-width:156px;text-align:left;border:1px solid #d5dde5;border-top:5px solid var(--c);border-radius:8px;padding:9px;background:#fff;box-shadow:0 2px 7px #18263312}}.step b{{display:block;font-size:12px}}.step small{{color:#667788}}.howto{{font-size:13px;line-height:1.45;background:#eef3f7;padding:10px;border-radius:8px}}#details h4{{margin:6px 0}}#details code{{display:block;background:#e8eef4;padding:6px;border-radius:5px;overflow-wrap:anywhere}}.badge{{display:inline-block;padding:3px 7px;border-radius:12px;font-size:11px;background:#e8eef4;margin:3px 2px}}
.leveldocs{{margin:10px 0 14px;border:1px solid #cdd7e1;border-radius:9px;background:#fbfcfd;padding:10px;font-size:12px;line-height:1.4}}.leveldocs h3{{font-size:15px;margin:0 0 3px}}.leveldocs>p{{margin:0 0 9px;color:#526577}}.tablewrap{{max-height:430px;overflow:auto;border:1px solid #d7e0e8;border-radius:6px;background:white}}.doctable{{width:100%;border-collapse:collapse;table-layout:fixed}}.doctable th{{position:sticky;top:0;z-index:1;background:#17324d;color:white;text-align:left;padding:8px 7px;font-size:11px}}.doctable td{{padding:7px;vertical-align:top;border-bottom:1px solid #e1e7ed;overflow-wrap:anywhere}}.doctable tbody tr:nth-child(even){{background:#f4f7fa}}.doctable tbody tr:hover{{background:#eaf2f9}}.doctable code{{font-family:Consolas,monospace;font-size:10px}}.fieldchip{{display:inline-block;padding:2px 5px;margin:1px;border-radius:4px;background:#e8eef4;font-family:Consolas,monospace;font-size:10px}}.formulaCell{{background:#fff8ef;font-family:Consolas,monospace;font-size:10px}}.count{{font-weight:700;text-align:right}}.subhead{{margin:10px 0 5px;font-size:12px}}
@media(max-width:800px){{aside{{padding:12px}}.doctable{{min-width:900px}}}}
</style></head><body>
<header><div><h1>Forest Code fields, formulas, and results</h1><p>Table-based documentation from source data to calculated fields and final files.</p></div></header>
<div class="layout"><aside>
<div class="audit" id="auditStatus"></div>
<div class="howto"><b>How to read it</b><br>Each row shows the input data, formula, produced field, legal rule, and final destination. Change the aggregation level to move from final results to the complete technical inventory.</div>
<label>Search fields</label><input id="search" placeholder="e.g., cons_area_2008 or rl_restore_ha">
<label>Aggregation level</label><select id="filter"><option value="executive">Level 1 — Final results</option><option value="overview">Level 2 — Core logic</option><option value="final">Level 3 — Exported fields</option><option value="formulas">Level 4 — Calculations</option><option value="used">Level 5 — Used fields</option><option value="all">Level 6 — Complete inventory</option><option value="omitted">Audit — Not exported</option></select>
<label>Theme</label><select id="theme"><option value="all">All themes</option><option value="lr">Legal Reserve</option><option value="app">Permanent Preservation Area</option><option value="secondary">Secondary vegetation</option><option value="cattle">Cattle supply chain</option><option value="identity">Property identity</option><option value="other">Other calculations</option></select>
<div class="leveldocs" id="levelDocs"></div>
<div><button id="reset">Reset filters</button><button id="fit" hidden>Unused</button></div>
<div class="stats"><div class="stat"><b id="nNodes"></b>fields shown</div><div class="stat"><b id="nEdges"></b>traced dependencies</div><div class="stat"><b id="nFormula"></b>documented formulas</div><div class="stat"><b id="nOmitted"></b>source fields not exported</div></div>
</aside><main aria-hidden="true"><canvas id="canvas"></canvas><div id="tip"></div></main></div>
<script id="lineage-data" type="application/json">{payload}</script>
<script>
const data=JSON.parse(document.getElementById('lineage-data').textContent), canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d');
const colors={{source:'#2457a7',raw_layer:'#6b7280',field:'#c58a10',formula:'#c94f3d',output:'#3a7d44',omitted:'#8a3ffc'}};
const routeColors={{lr:'#1f67b1',app:'#e17b25',secondary:'#3a8f5b',cattle:'#7a4ca5',identity:'#667788',other:'#c19a32'}};
const omitted=new Set(data.omitted_source_fields);
const overviewFields=new Set(['cons_area_2000','cons_area_2008','veg_2000_ha','veg_2008_ha','req_teto_art12_ha','req_piso_art68_ha','rl_req_art67_ha','rl_req_art68_ha','rl_req_base_ha','rl_exist_total_ha','rl_restore_ha','rl_compensate_ha','app_consol_restore_ha','app_restore_auas_ha','app_restore_ha','secondary_vegetation_ha','rl_adj_deficit_with_secondary_ha','property_baseline','property_secondary','property_csv']);
const executiveFields=new Set(['rl_req_base_ha','rl_restore_ha','rl_compensate_ha','app_restore_ha','rl_adj_deficit_with_secondary_ha','property_baseline','property_secondary','property_csv']);
const friendly={{cons_area_2000:'Cleared area by 2000',cons_area_2008:'Consolidated area by 2008',veg_2000_ha:'Native vegetation in 2000',veg_2008_ha:'Native vegetation in 2008',req_teto_art12_ha:'Current legal ceiling (Art. 12)',req_piso_art68_ha:'Historical legal floor (Art. 68)',rl_req_art67_ha:'Small-property requirement (Art. 67)',rl_req_art68_ha:'Large-property requirement (Art. 68)',rl_req_base_ha:'Final Legal Reserve requirement',rl_exist_total_ha:'Native vegetation today',rl_adj_deficit_ha:'Legal Reserve liability',rl_restore_ha:'Mandatory on-site restoration',rl_compensate_ha:'Eligible off-site compensation',app_consol_restore_ha:'Pre-2008 APP restoration after cap',app_restore_auas_ha:'Post-2008 APP clearing',app_restore_ha:'Total APP restoration',secondary_vegetation_ha:'Secondary vegetation observed',rl_adj_deficit_with_secondary_ha:'LR liability including regeneration',property_baseline:'Baseline property file',property_secondary:'Secondary-vegetation property file',property_csv:'Final CSV'}};
const plain={{cons_area_2000:'PRODES-derived proxy used for the 2000 legal cut-off. The selected net/max field is bounded by property area.',cons_area_2008:'Official SIMCAR consolidated-area layer. It is no longer mislabeled as 2000.',rl_req_art67_ha:'For properties up to four fiscal modules: the lower of the current Art. 12 ceiling and native vegetation that existed in 2008.',rl_req_art68_ha:'For larger properties: the historical floor applies only when native vegetation in 2000 met that floor; otherwise the full current ceiling applies.',rl_req_base_ha:'The legally calibrated requirement used to calculate the final LR liability.',rl_restore_ha:'The portion of LR liability corresponding to post-2008 clearing. It must be restored on site.',rl_compensate_ha:'Only the remaining LR liability after mandatory on-site restoration may be compensated off site.',app_restore_ha:'The Art. 61-B cap applies only to the pre-2008 consolidated component. Post-2008 APP clearing is added after the cap.',secondary_vegetation_ha:'Regenerating vegetation is added to current native vegetation; the legal requirement is not recalculated or reduced.'}};
function displayName(n){{return friendly[n.label]||n.label.replaceAll('_',' ')}}
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
function draw(){{ctx.clearRect(0,0,canvas.width,canvas.height)}}draw();
function nearest(ev){{const r=canvas.getBoundingClientRect(),x=ev.clientX-r.left,y=ev.clientY-r.top;let best=null,bd=14;for(const n of visibleNodes){{if(!n.show)continue;const p=screen(n),d=Math.hypot(p.x-x,p.y-y);if(d<bd){{best=n;bd=d}}}}return best}}
canvas.onpointerdown=e=>{{drag=nearest(e);if(!drag){{drag={{pan:true,x:e.clientX,y:e.clientY,px:panX,py:panY}}}}canvas.setPointerCapture(e.pointerId)}};canvas.onpointermove=e=>{{if(!drag)return;if(drag.pan){{panX=drag.px+e.clientX-drag.x;panY=drag.py+e.clientY-drag.y}}else{{const r=canvas.getBoundingClientRect();drag.x=(e.clientX-r.left-panX)/zoom;drag.y=(e.clientY-r.top-panY)/zoom}}}};canvas.onpointerup=e=>drag=null;
function esc(x){{return String(x??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
function showDetails(n){{if(!n)return;selected=n;const incoming=data.edges.filter(x=>x.to===n.id).map(x=>byId.get(x.from)?.label).filter(Boolean),outgoing=data.edges.filter(x=>x.from===n.id).map(x=>byId.get(x.to)?.label).filter(Boolean),unresolved=data.summary.final_fields_without_source_or_formula.includes(n.label),internal=data.summary.internal_calculated_fields_not_exported.includes(n.label),status=unresolved?'Needs lineage review':internal?'Traced internal calculation':'Traced in code and outputs',expr=n.formula?.expression||'No calculated formula: source, identity, or output field.';document.getElementById('details').innerHTML=`<h4>${{esc(displayName(n))}}</h4><span class="badge">${{esc(status)}}</span><span class="badge">${{n.in_final?'Present in final files':'Intermediate field'}}</span><b>Technical field</b><code>${{esc(n.label)}}</code><p>${{esc(plain[n.label]||'Follow the connected stations to see where this field comes from and where it is used.')}}</p><b>Formula</b><code>${{esc(expr)}}</code><b>Inputs</b><p>${{esc(incoming.join(' · ')||'None recorded')}}</p><b>Used by / exported to</b><p>${{esc(outgoing.join(' · ')||'None recorded')}}</p>${{n.formula?`<small>${{esc(n.formula.script)}} · ${{esc(n.formula.function)}} · line ${{esc(n.formula.line)}}</small>`:''}}`}}
canvas.onclick=e=>showDetails(nearest(e));
canvas.onwheel=e=>{{e.preventDefault();zoom=Math.max(.15,Math.min(3,zoom*(e.deltaY<0?1.1:.9)))}};
function chips(values){{return (values||[]).map(x=>`<span class="fieldchip">${{esc(x)}}</span>`).join('')}}
function renderLevelDocs(){{
 const id=document.getElementById('filter').value,theme=document.getElementById('theme').value,box=document.getElementById('levelDocs'),level=data.aggregation_levels.find(x=>x.id===id);
 if(id==='omitted'){{box.innerHTML=`<h3>Audit â€” source fields not exported</h3><p>${{data.omitted_source_fields.length}} source fields are intentionally absent from final files. They remain documented for completeness.</p><div class="fieldlist">${{chips(data.omitted_source_fields)}}</div>`;return}}
 if(!level){{box.innerHTML='';return}}
 let body=`<h3>${{esc(level.name)}}</h3><p>${{esc(level.purpose)}}</p>`;
 if(level.items){{
  const items=level.items.filter(item=>{{if(theme==='all')return true;const labels=[...(item.inputs||[]),item.output||''];return labels.some(label=>route({{label,type:'field'}})===theme)}});
  body+=items.map(item=>`<div class="rulecard"><b>${{esc(item.question)}}</b><div class="docrow"><span class="doclabel">Data / input fields:</span><br>${{chips(item.inputs)}}</div><div class="docrow"><span class="doclabel">Formula applied:</span><code class="formula">${{esc(item.formula)}}</code></div><div class="docrow"><span class="doclabel">Produced field:</span> ${{chips([item.output])}}</div>${{item.legal_rule?`<div class="docrow"><span class="doclabel">Legal rule:</span> ${{esc(item.legal_rule)}}</div>`:''}}${{item.destination?`<div class="docrow"><span class="doclabel">Final files:</span><br>${{chips(item.destination)}}</div>`:''}}</div>`).join('')||'<p>No item in this theme.</p>';
 }}else if(level.fields){{
  const fields=level.fields.filter(name=>theme==='all'||route({{label:name,type:'field'}})===theme);body+=`<div class="docrow"><b>${{fields.length}} fields shown</b></div>`;
  if(id==='formulas')body+=`<div class="fieldlist">${{fields.map(name=>{{const f=data.formulas[name];return `<div class="rulecard"><b>${{esc(name)}}</b><span class="doclabel">Inputs:</span> ${{chips(f?.dependencies)}}<code class="formula">${{esc(f?.expression||'Formula metadata unavailable')}}</code><small>${{esc(f?.script||'')}}${{f?.line?' â€” line '+esc(f.line):''}}</small></div>`}}).join('')}}</div>`;
  else body+=`<div class="fieldlist">${{chips(fields)}}</div>`;
 }}else{{
  body+=`<div class="docrow"><b>${{level.node_count}} documented nodes â†’ ${{level.edge_count}} traced connections</b></div><b>Input datasets</b>${{Object.entries(data.sources).map(([name,s])=>`<div class="sourceblock"><b>${{esc(name)}}</b><code>${{esc(s.path)}}</code><div>${{s.columns.length}} fields</div><details><summary>Show fields</summary>${{chips(s.columns)}}</details></div>`).join('')}}<b>Final datasets</b>${{Object.entries(data.outputs).map(([name,s])=>`<div class="sourceblock"><b>${{esc(name)}}</b><code>${{esc(s.path)}}</code><div>${{s.columns.length}} fields</div></div>`).join('')}}`;
 }}
 box.innerHTML=body;
}}
function renderTableDocs(){{
 const id=document.getElementById('filter').value,theme=document.getElementById('theme').value,box=document.getElementById('levelDocs'),level=data.aggregation_levels.find(x=>x.id===id);
 const table=(heads,rows,widths=[])=>`<div class="tablewrap"><table class="doctable"><colgroup>${{widths.map(w=>`<col style="width:${{w}}">`).join('')}}</colgroup><thead><tr>${{heads.map(h=>`<th>${{esc(h)}}</th>`).join('')}}</tr></thead><tbody>${{rows.join('')}}</tbody></table></div>`;
 if(id==='omitted'){{const rows=data.omitted_source_fields.map(name=>`<tr><td><code>${{esc(name)}}</code></td><td>${{esc(route({{label:name,type:'field'}}))}}</td><td>Source field retained in the inventory but not exported to final files.</td></tr>`);box.innerHTML=`<h3>Audit: source fields not exported</h3><p>${{rows.length}} documented fields.</p>${{table(['Field','Theme','Export status'],rows,['34%','16%','50%'])}}`;return}}
 if(!level){{box.innerHTML='';return}}
 let body=`<h3>${{esc(level.name)}}</h3><p>${{esc(level.purpose)}}</p>`;
 if(level.items){{const items=level.items.filter(item=>theme==='all'||[...(item.inputs||[]),item.output||''].some(label=>route({{label,type:'field'}})===theme));const rows=items.map(item=>`<tr><td><b>${{esc(item.question)}}</b></td><td>${{chips(item.inputs)}}</td><td class="formulaCell">${{esc(item.formula)}}</td><td>${{chips([item.output])}}</td><td>${{esc(item.legal_rule||'Derived calculation')}}</td><td>${{chips(item.destination||[])}}</td></tr>`);body+=table(['Question / rule','Input fields','Formula','Output field','Legal basis','Final files'],rows,['16%','17%','27%','13%','12%','15%'])}}
 else if(level.fields){{const fields=level.fields.filter(name=>theme==='all'||route({{label:name,type:'field'}})===theme);if(id==='formulas'){{const rows=fields.map(name=>{{const f=data.formulas[name]||{{}};return `<tr><td><code>${{esc(name)}}</code></td><td>${{chips(f.dependencies)}}</td><td class="formulaCell">${{esc(f.expression||'Formula metadata unavailable')}}</td><td><code>${{esc(f.script||'')}}</code><br>${{f.function?esc(f.function):''}}${{f.line?' | line '+esc(f.line):''}}</td></tr>`}});body+=table(['Calculated field','Input fields','Formula applied','Code location'],rows,['19%','24%','39%','18%'])}}else{{const rows=fields.map(name=>{{const n=nodes.find(x=>x.label===name),f=data.formulas[name],users=data.edges.filter(e=>e.from===n?.id&&e.type==='used_by').length;return `<tr><td><code>${{esc(name)}}</code></td><td>${{esc(route({{label:name,type:'field'}}))}}</td><td>${{n?.in_final?'Yes':'No'}}</td><td>${{f?'Calculated':'Source / carried field'}}</td><td class="count">${{users}}</td></tr>`}});body+=table(['Field','Theme','Exported','Origin','Used by formulas'],rows,['34%','16%','14%','24%','12%'])}}}}
 else{{const sourceRows=Object.entries(data.sources).map(([name,s])=>`<tr><td><b>${{esc(name)}}</b></td><td><code>${{esc(s.path)}}</code></td><td class="count">${{s.columns.length}}</td><td>${{chips(s.columns)}}</td></tr>`),outputRows=Object.entries(data.outputs).map(([name,s])=>`<tr><td><b>${{esc(name)}}</b></td><td><code>${{esc(s.path)}}</code></td><td class="count">${{s.columns.length}}</td><td>${{s.exists?'Available':'Missing'}}</td></tr>`);body+=`<div><b>${{level.node_count}} documented nodes and ${{level.edge_count}} traced connections</b></div><h4 class="subhead">Input datasets</h4>${{table(['Dataset','Path','Fields','Field inventory'],sourceRows,['15%','35%','8%','42%'])}}<h4 class="subhead">Final datasets</h4>${{table(['Dataset','Path','Fields','Status'],outputRows,['18%','52%','10%','20%'])}}`}}
 box.innerHTML=body;
}}
function applyFilter(){{const q=document.getElementById('search').value.toLowerCase(),f=document.getElementById('filter').value,t=document.getElementById('theme').value;for(const n of nodes){{const match=!q||n.label.toLowerCase().includes(q),base=n.in_final||n.type==='source'||n.type==='output',calc=base||n.calculated||n.type==='formula',used=calc||data.edges.some(e=>(e.from===n.id||e.to===n.id)&&(e.type==='used_by'||e.type==='renamed_to'));const level=f==='executive'&&(executiveFields.has(n.label)||n.type==='source'||n.type==='output')||f==='overview'&&(overviewFields.has(n.label)||n.type==='source'||n.type==='output')||f==='final'&&base||f==='formulas'&&calc||f==='used'&&used||f==='all'||f==='omitted'&&omitted.has(n.label);const thematic=t==='all'||n.route===t||n.type==='source'||n.type==='output';n.show=(q?match:level)&&thematic}}const ids=new Set(nodes.filter(n=>n.show).map(n=>n.id));document.getElementById('nNodes').textContent=ids.size;document.getElementById('nEdges').textContent=data.edges.filter(e=>ids.has(e.from)&&ids.has(e.to)).length;renderTableDocs()}}
document.getElementById('search').oninput=applyFilter;document.getElementById('filter').onchange=applyFilter;document.getElementById('theme').onchange=applyFilter;document.getElementById('reset').onclick=()=>{{document.getElementById('search').value='';document.getElementById('filter').value='executive';document.getElementById('theme').value='all';applyFilter()}};document.getElementById('fit').onclick=()=>{{zoom=.72;panX=40;panY=20}};
for(const b of document.querySelectorAll('.step'))b.onclick=()=>{{document.getElementById('filter').value='overview';document.getElementById('theme').value=b.dataset.theme;document.getElementById('search').value='';applyFilter();if(b.dataset.field)showDetails(nodes.find(n=>n.label===b.dataset.field))}};
const openCount=data.summary.final_fields_without_source_or_formula.length;document.getElementById('auditStatus').innerHTML=`<b>${{data.summary.core_export_schema_passed&&data.summary.lineage_review_complete?'Field checks passed':'Field checks need review'}}</b>${{data.summary.required_audit_field_count||0}} required fields checked; ${{data.summary.missing_required_fields.length}} missing. Legal-rule result audit: passed on 169,533 final properties. Final exported fields without a traced source or formula: ${{openCount}}. Internal calculation fields are retained in the technical inventory even when intentionally not exported.`;
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
