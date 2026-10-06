"""Statewide physical-consistency audit for Forest Code property results.

This audit intentionally does not repair values.  A scalar clamp can hide a
spatial error: the legally meaningful temporal rule is geometry(2000) within
geometry(2008), and APP cover classes must be mutually exclusive geometries.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "out/table/forest_code_mt_priority_consolidated_with_secondary_20261006.parquet"
OUT = ROOT / "qa/statewide_app_temporal_consistency_20261006"
EPS_HA = 0.01


def main() -> None:
    cols = [
        "CODIGO_CAR", "car_join", "input_file_type", "area_ha_car", "MODULOS_FI",
        "cons_area_2000", "cons_area_2008", "veg_2000_ha", "veg_2008_ha",
        "app_req_ha", "app_preserved_ha", "appd_declared_ha", "app_fnl_cs08",
        "app_fnl_auas", "app_restore_auas_ha", "app_consolidated_ha",
        "app_gross_deficit_ha", "app_restore_ha", "avn_declared_ha",
        "app_fnl_avn24", "rl_req_base_ha", "rl_exist_total_ha",
        "rl_adj_deficit_ha", "rl_restore_ha", "rl_compensate_ha",
        "secondary_vegetation_ha", "rl_exist_total_with_secondary_ha",
        "calc_deficit_total_ha", "calc_deficit_total_with_secondary_ha",
        "app_partition_total_ha", "app_partition_native_ha",
        "app_partition_pre2008_ha", "app_partition_post2008_ha",
    ]
    d = pd.read_parquet(SOURCE, columns=cols)
    n = len(d)
    num = lambda c: pd.to_numeric(d[c], errors="coerce").fillna(0.0)
    area, c00, c08, app = map(num, ["area_ha_car", "cons_area_2000", "cons_area_2008", "app_req_ha"])

    # These three displayed inputs are diagnostic only.  They are not a valid
    # APP partition for validated/digital records: AVN and APPD can overlap APP
    # and each other and APPD denotes a restoration strip, not all pre-2008 loss.
    displayed_native = num("app_partition_native_ha")
    displayed_pre08 = num("app_partition_pre2008_ha")
    displayed_post08 = num("app_partition_post2008_ha")
    displayed_app_sum = displayed_native + displayed_pre08 + displayed_post08

    checks = {
        "negative_area": area < -EPS_HA,
        "cons_2000_above_property": c00 > area + EPS_HA,
        "cons_2008_above_property": c08 > area + EPS_HA,
        "cons_2000_above_cons_2008": c00 > c08 + EPS_HA,
        "veg_2000_formula_mismatch": (num("veg_2000_ha") - (area - c00).clip(lower=0)).abs() > EPS_HA,
        "veg_2008_formula_mismatch": (num("veg_2008_ha") - (area - c08).clip(lower=0)).abs() > EPS_HA,
        "app_above_property": app > area + EPS_HA,
        "app_preserved_above_app": num("app_preserved_ha") > app + EPS_HA,
        "app_post2008_above_app": num("app_restore_auas_ha") > app + EPS_HA,
        "app_restore_above_app": num("app_restore_ha") > app + EPS_HA,
        "app_displayed_partition_not_closed": (displayed_app_sum - app).abs() > EPS_HA,
        "app_model_components_above_app": (num("app_preserved_ha") + num("app_consolidated_ha") + num("app_restore_auas_ha")) > app + EPS_HA,
        "rl_split_mismatch": (num("rl_restore_ha") + num("rl_compensate_ha") - num("rl_adj_deficit_ha")).abs() > EPS_HA,
        "secondary_stock_above_property": num("rl_exist_total_with_secondary_ha") > area + EPS_HA,
        "baseline_deficit_above_property": num("calc_deficit_total_ha") > area + EPS_HA,
        "secondary_deficit_above_property": num("calc_deficit_total_with_secondary_ha") > area + EPS_HA,
    }

    detail = d[["CODIGO_CAR", "car_join", "input_file_type", "area_ha_car", "MODULOS_FI"]].copy()
    detail["app_displayed_sum_ha"] = displayed_app_sum
    detail["app_displayed_closure_error_ha"] = displayed_app_sum - app
    detail["cons_2000_minus_2008_ha"] = c00 - c08
    for name, mask in checks.items():
        detail[name] = mask
    detail["failed_check_count"] = detail[list(checks)].sum(axis=1)
    failures = detail.loc[detail.failed_check_count > 0].copy()

    rows = []
    for name, mask in checks.items():
        rows.append({"check": name, "failed_properties": int(mask.sum()), "total_properties": n,
                     "failure_rate": float(mask.mean())})
        for src, smask in d.groupby("input_file_type", observed=True).groups.items():
            idx = pd.Index(smask)
            rows.append({"check": name, "input_file_type": str(src),
                         "failed_properties": int(mask.loc[idx].sum()), "total_properties": len(idx),
                         "failure_rate": float(mask.loc[idx].mean())})
    summary = pd.DataFrame(rows)

    OUT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT / "01_check_summary.csv", index=False)
    failures.to_csv(OUT / "02_property_failures.csv", index=False)
    payload = {
        "source": str(SOURCE), "rows": n, "tolerance_ha": EPS_HA,
        "statewide": {r["check"]: {"failed_properties": r["failed_properties"],
                       "failure_rate": r["failure_rate"]} for r in rows if "input_file_type" not in r},
        "interpretation": {
            "temporal": "A hectare-only failure proves inconsistency; a pass does not prove spatial containment. Full proof requires geometry(2000) difference geometry(2008) to be empty.",
            "app": "Displayed AVN/APPD/AUAS fields are not mutually exclusive APP land-cover classes for validated/digital sources. Closure requires APP-clipped, non-overlapping native/pre-2008/post-2008 geometries.",
        },
    }
    (OUT / "03_audit_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["statewide"], indent=2))


if __name__ == "__main__":
    main()
