"""Independently reconcile final CSV, Excel, and Parquet package counts/totals."""

from __future__ import annotations

import csv
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[2]
KEY = "priority_key"
METRICS = (
    "area_ha_car",
    "cons_area_2000",
    "cons_area_2008",
    "rl_adj_deficit_ha",
    "rl_restore_ha",
    "rl_compensate_ha",
    "app_restore_ha",
    "calc_deficit_total_ha",
    "secondary_vegetation_ha",
    "calc_deficit_total_with_secondary_ha",
)


def number(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def scan_csvs(paths: list[Path]) -> dict:
    rows = 0
    columns = None
    keys: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    sums = Counter()
    violations = Counter()
    status = Counter()
    for path in paths:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if columns is None:
                columns = len(reader.fieldnames or [])
            elif columns != len(reader.fieldnames or []):
                violations["inconsistent_column_count"] += 1
            for row in reader:
                rows += 1
                keys[row.get(KEY, "")] += 1
                sources[row.get("input_file_type", "")] += 1
                for metric in METRICS:
                    sums[metric] += number(row.get(metric))
                status["baseline_noncompliant"] += number(row.get("calc_deficit_total_ha")) > 1e-9
                status["secondary_noncompliant"] += number(row.get("calc_deficit_total_with_secondary_ha")) > 1e-9
                status["lr_noncompliant"] += number(row.get("rl_adj_deficit_ha")) > 1e-9
                status["app_noncompliant"] += number(row.get("app_restore_ha")) > 1e-9
                area = number(row.get("area_ha_car"))
                for field in ("cons_area_2000", "cons_area_2008", "calc_deficit_total_ha", "calc_deficit_total_with_secondary_ha"):
                    if number(row.get(field)) > area + 1e-7:
                        violations[f"{field}_gt_property"] += 1
                if abs(number(row.get("rl_adj_deficit_ha")) - number(row.get("rl_restore_ha")) - number(row.get("rl_compensate_ha"))) > 1e-6:
                    violations["rl_pathway_mismatch"] += 1
                expected = min(number(row.get("rl_adj_deficit_ha")) + number(row.get("app_restore_ha")), area)
                if abs(number(row.get("calc_deficit_total_ha")) - expected) > 1e-6:
                    violations["baseline_total_mismatch"] += 1
    return {
        "files": len(paths),
        "rows": rows,
        "columns": columns,
        "unique_keys": len(keys),
        "duplicate_rows": sum(count - 1 for count in keys.values() if count > 1),
        "blank_keys": keys.get("", 0),
        "sources": dict(sources),
        "metric_sums_ha": {key: round(sums[key], 6) for key in METRICS},
        "property_counts": dict(status),
        "violations": dict(violations),
    }


def scan_excels(paths: list[Path]) -> dict:
    rows = formulas = 0
    columns = set()
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml")
        rows += max(sheet.count(b"<row") - 1, 0)
        formulas += sheet.count(b"<f")
        header = sheet.split(b"</row>", 1)[0]
        columns.add(len(re.findall(rb"<c\b", header)))
    return {"files": len(paths), "rows": rows, "column_counts": sorted(columns), "formula_cells": formulas}


def main() -> None:
    raw_source = scan_csvs([ROOT / "outputs" / "codigo_florestal_mt_inputs_completos.csv"])
    raw_parts = scan_csvs(sorted((ROOT / "deliverables" / "02_csv_raw").glob("*.csv")))
    result_parts = scan_csvs(sorted((ROOT / "deliverables" / "02_csv").glob("*.csv")))
    excels = scan_excels(sorted((ROOT / "outputs").glob("codigo_florestal_mt_completo_formulas_parte_*.xlsx")))
    parquet_paths = sorted((ROOT / "out" / "table").glob("forest_code_mt_priority_consolidated*.parquet"))
    parquets = {
        path.name: {"rows": pq.ParquetFile(path).metadata.num_rows, "columns": pq.ParquetFile(path).metadata.num_columns}
        for path in parquet_paths
    }
    report = {
        "raw_source": raw_source,
        "raw_csv_parts": raw_parts,
        "result_csv_parts": result_parts,
        "excel_parts": excels,
        "property_parquets": parquets,
        "reconciliations": {
            "raw_source_equals_raw_parts": raw_source == raw_parts | {"files": raw_source["files"]},
            "property_rows_agree": len({raw_source["rows"], raw_parts["rows"], result_parts["rows"], excels["rows"]}) == 1,
            "result_totals_equal_raw_source": raw_source["metric_sums_ha"] == result_parts["metric_sums_ha"],
        },
    }
    target = ROOT / "qa" / "final_package_number_audit_20260930.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
