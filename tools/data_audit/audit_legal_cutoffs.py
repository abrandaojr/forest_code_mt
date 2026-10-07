from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "out" / "table" / "forest_code_mt_priority_consolidated_20261007.parquet"
SECONDARY = ROOT / "out" / "table" / "forest_code_mt_priority_consolidated_with_secondary_20261007.parquet"
OUT = ROOT / "qa" / "legal_cutoff_audit_20261007.json"


def num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce").fillna(0)


def maxdiff(a, b) -> float:
    return float(np.nanmax(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float))))


def main() -> None:
    d = pd.read_parquet(BASE)
    area, c00, c08 = num(d, "area_ha_car"), num(d, "cons_area_2000"), num(d, "cons_area_2008")
    teto, piso = num(d, "req_teto_art12_ha"), num(d, "req_piso_art68_ha")
    expected_art67 = np.minimum(teto, num(d, "veg_2008_ha"))
    expected_art68 = np.where(d["art68_legal_2000"].astype(bool), piso, teto)
    expected_base = np.where(d["art67_small_prop"].astype(bool), expected_art67, expected_art68)
    deficit = np.maximum(expected_base - num(d, "rl_exist_total_ha"), 0)
    expected_restore = np.minimum(np.maximum(num(d, "auas_post2008"), 0), deficit)
    expected_comp = np.maximum(deficit - expected_restore, 0)
    expected_app = np.minimum(num(d, "app_consol_restore_ha") + num(d, "app_restore_auas_ha"), num(d, "app_gross_deficit_ha"))
    expected_total = np.minimum(deficit + expected_app, area)
    expected_gross_total = np.minimum(num(d, "rl_gross_deficit_ha") + num(d, "app_gross_deficit_ha"), area)

    checks = {
        "cons_area_2000_not_above_property": int((c00 > area + 1e-8).sum()),
        "cons_area_2008_not_above_property": int((c08 > area + 1e-8).sum()),
        "negative_historical_area_cells": int(((c00 < -1e-8) | (c08 < -1e-8)).sum()),
        "veg_2000_identity_max_diff": maxdiff(num(d, "veg_2000_ha"), np.maximum(area - c00, 0)),
        "veg_2008_identity_max_diff": maxdiff(num(d, "veg_2008_ha"), np.maximum(area - c08, 0)),
        "art67_requirement_max_diff": maxdiff(num(d, "rl_req_art67_ha"), expected_art67),
        "art68_requirement_max_diff": maxdiff(num(d, "rl_req_art68_ha"), expected_art68),
        "base_requirement_max_diff": maxdiff(num(d, "rl_req_base_ha"), expected_base),
        "rl_deficit_max_diff": maxdiff(num(d, "rl_adj_deficit_ha"), deficit),
        "rl_restore_max_diff": maxdiff(num(d, "rl_restore_ha"), expected_restore),
        "rl_compensate_max_diff": maxdiff(num(d, "rl_compensate_ha"), expected_comp),
        "app_consolidated_above_cap": int((num(d, "app_consol_restore_ha") > num(d, "app_cap_ha") + 1e-8).sum()),
        "app_restore_post_cap_max_diff": maxdiff(num(d, "app_restore_ha"), expected_app),
        "current_vegetation_above_property": int((num(d, "rl_exist_total_ha") > area + 1e-8).sum()),
        "final_total_above_property": int((num(d, "calc_deficit_total_ha") > area + 1e-8).sum()),
        "gross_total_above_property": int((num(d, "calc_gross_deficit_total_ha") > area + 1e-8).sum()),
        "final_total_formula_max_diff": maxdiff(num(d, "calc_deficit_total_ha"), expected_total),
        "gross_total_formula_max_diff": maxdiff(num(d, "calc_gross_deficit_total_ha"), expected_gross_total),
    }
    if SECONDARY.exists():
        s = pd.read_parquet(SECONDARY)
        expected_secondary = np.maximum(num(s, "rl_req_base_ha") - num(s, "rl_exist_total_with_secondary_ha"), 0)
        checks["secondary_deficit_max_diff"] = maxdiff(num(s, "rl_adj_deficit_with_secondary_ha"), expected_secondary)
        checks["secondary_total_vegetation_above_property"] = int(
            (num(s, "rl_exist_total_with_secondary_ha") > num(s, "area_ha_car") + 1e-8).sum()
        )
        checks["secondary_effective_above_available_space"] = int(
            (num(s, "secondary_vegetation_ha") > (num(s, "area_ha_car") - num(s, "rl_exist_total_ha")).clip(lower=0) + 1e-8).sum()
        )
        checks["secondary_final_total_above_property"] = int(
            (num(s, "calc_deficit_total_with_secondary_ha") > num(s, "area_ha_car") + 1e-8).sum()
        )

    failures = {k: v for k, v in checks.items() if abs(v) > 1e-7}
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": str(BASE.relative_to(ROOT)).replace("\\", "/"),
        "rows": len(d),
        "input_rows": d["input_file_type"].value_counts().to_dict(),
        "proxy_2000_source_counts": d["cons_area_2000_source"].value_counts(dropna=False).to_dict(),
        "proxy_2000_missing_rows": int(d["cons_area_2000_proxy_missing"].astype(bool).sum()),
        "checks": checks,
        "passed": not failures,
        "failures": failures,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
