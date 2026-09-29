from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[2]
PRE = ROOT / "data" / "pre"
TABLES = ROOT / "out" / "table"
QA = ROOT / "qa"
DATE = "20260818"

SOURCES = {
    "simcar_validado": PRE / "car_validated" / f"car_atp_joined_{DATE}.parquet",
    "simcar_digital": PRE / "car_digital" / f"car_atp_joined_{DATE}.parquet",
    "simcar_proxy": PRE / "car_proxy" / f"car_atp_joined_{DATE}.parquet",
}

# Inputs that must remain inspectable in final property-level results even when
# a downstream formula does not directly reference every one of them.
REQUIRED_AUDIT_FIELDS = {
    "MODULOS_FI",
    "area_ha_car",
    "radam_FLORESTA_ha",
    "radam_CERRADO_ha",
    "radam_forest_nveg24_ha",
    "radam_cerrado_nveg24_ha",
    "cons_area_2000",
    "cons_area_2008",
    "auas_post2008",
    "app",
    "app_fnl_auas",
    "app_fnl_avn24",
    "app_fnl_cs08",
    "appd_lte1mf_cs08",
    "appd_1a2mf_cs08",
    "appd_2a4mf_cs08",
    "appd_4a10mf_cs08",
    "appd_gt10mf_cs08",
    "arl_declared_ha",
    "avn_declared_ha",
    "appd_declared_ha",
    "apprl_declared_ha",
    "au_declared_ha",
}


def parquet_columns(path: Path) -> list[str]:
    return pq.ParquetFile(path).schema_arrow.names


def metric_cols_from_code() -> set[str]:
    tree = ast.parse((ROOT / "code" / "_20_build_priority.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "METRIC_COLS":
                    return set(ast.literal_eval(node.value))
    raise RuntimeError("METRIC_COLS not found")


def main() -> None:
    final_path = TABLES / f"forest_code_mt_priority_consolidated_with_secondary_{DATE}.parquet"
    final_cols = set(parquet_columns(final_path))
    metric_cols = metric_cols_from_code()

    rows: list[dict[str, object]] = []
    source_presence: dict[str, list[str]] = {}
    for source, path in SOURCES.items():
        cols = set(parquet_columns(path))
        source_presence[source] = sorted(REQUIRED_AUDIT_FIELDS & cols)
        for field in sorted(REQUIRED_AUDIT_FIELDS):
            rows.append(
                {
                    "field": field,
                    "source": source,
                    "present_in_source": field in cols,
                    "included_in_metric_cols": field in metric_cols,
                    "present_in_final": field in final_cols,
                    "status": (
                        "ok"
                        if field in final_cols
                        else "missing_final"
                        if field in cols or field in REQUIRED_AUDIT_FIELDS
                        else "not_applicable"
                    ),
                }
            )

    QA.mkdir(parents=True, exist_ok=True)
    csv_path = QA / f"final_export_schema_audit_{DATE}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    missing = sorted(REQUIRED_AUDIT_FIELDS - final_cols)
    report = {
        "final_file": str(final_path),
        "final_column_count": len(final_cols),
        "required_audit_field_count": len(REQUIRED_AUDIT_FIELDS),
        "missing_required_fields": missing,
        "all_required_fields_present": not missing,
        "source_presence": source_presence,
        "csv_evidence": str(csv_path),
    }
    json_path = QA / f"final_export_schema_audit_{DATE}.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if missing:
        raise SystemExit(f"Missing required final fields: {missing}")


if __name__ == "__main__":
    main()
