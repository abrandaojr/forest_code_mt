from __future__ import annotations

from pathlib import Path

import pandas as pd

import _00_paths as paths


paths.set_env()

ROOT = paths.ROOT
RAW = paths.RAW
PRE = paths.PRE
PROC = paths.PROC
OUT = paths.OUT
TABLES = paths.TABLES
FIGURES = paths.FIGURES
REPORTS = paths.REPORTS
QGIS = paths.QGIS
QA = paths.QC
DOCS = paths.DOCS
DATE = paths.RUN_DATE

SOURCE_ORDER = ["simcar_validado", "simcar_digital", "simcar_proxy"]
SOURCE_LABELS = {
    "simcar_validado": "SIMCAR validated",
    "simcar_digital": "SIMCAR digital",
    "simcar_proxy": "SIMCAR proxy",
}


def num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def dated(folder: Path, pattern: str, required: bool = True) -> Path | None:
    exact = folder / pattern.format(date=DATE)
    if exact.exists():
        return exact
    matches = sorted(folder.glob(pattern.format(date="*")), key=lambda p: p.stat().st_mtime, reverse=True)
    if matches:
        return matches[0]
    if required:
        raise FileNotFoundError(exact)
    return None


def table(pattern: str, required: bool = True) -> Path | None:
    return dated(TABLES, pattern, required)


def report(pattern: str, required: bool = True) -> Path | None:
    return dated(REPORTS, pattern, required)


def final_outputs() -> list[Path]:
    return [
        TABLES / f"forest_code_mt_priority_consolidated_{DATE}.parquet",
        TABLES / f"forest_code_mt_priority_consolidated_with_secondary_{DATE}.parquet",
        TABLES / f"forest_code_mt_priority_consolidated_with_secondary_{DATE}.csv",
        TABLES / f"forest_code_gta_final_mt_{DATE}.parquet",
        TABLES / f"masson_style_final_tables_figures_{DATE}.xlsx",
        REPORTS / f"forest_code_mt_final_report_{DATE}.docx",
        REPORTS / f"forest_code_mt_one_pager_diagnostic_{DATE}.png",
        REPORTS / f"diagnostico_codigo_florestal_mt_one_pager_{DATE}.png",
        REPORTS / f"forest_code_mt_interactive_one_pager_{DATE}.html",
        REPORTS / f"forest_code_mt_noncompliance_pdf_summary_{DATE}.html",
        REPORTS / f"forest_code_mt_noncompliance_pdf_summary_{DATE}.pdf",
    ]


def load_priority(with_secondary: bool = False) -> pd.DataFrame:
    suffix = "_with_secondary" if with_secondary else ""
    return pd.read_parquet(TABLES / f"forest_code_mt_priority_consolidated{suffix}_{DATE}.parquet")


def formula_checks(fc: pd.DataFrame) -> dict[str, object]:
    checks = {
        "priority_order": list(fc["input_file_type"].astype(str).drop_duplicates()),
        "net_formula_max_diff": float((num(fc, "calc_deficit_total_ha") - num(fc, "rl_adj_deficit_ha") - num(fc, "app_restore_ha")).abs().max()),
        "gross_formula_max_diff": float((num(fc, "calc_gross_deficit_total_ha") - num(fc, "rl_gross_deficit_ha") - num(fc, "app_gross_deficit_ha")).abs().max()),
        "rl_split_max_diff": float((num(fc, "rl_adj_deficit_ha") - num(fc, "rl_adj_deficit_forest_ha") - num(fc, "rl_adj_deficit_cerrado_ha")).abs().max()),
        "rl_pathway_max_diff": float((num(fc, "rl_adj_deficit_ha") - num(fc, "rl_restore_ha") - num(fc, "rl_compensate_ha")).abs().max()),
        "negative_core_cells": int((fc[[c for c in ["rl_adj_deficit_ha", "rl_restore_ha", "rl_compensate_ha", "app_restore_ha", "calc_deficit_total_ha"] if c in fc]].apply(pd.to_numeric, errors="coerce").fillna(0) < -1e-9).sum().sum()),
    }
    if {"calc_deficit_total_with_secondary_ha", "rl_adj_deficit_with_secondary_ha", "app_restore_ha"}.issubset(fc.columns):
        checks["secondary_formula_max_diff"] = float((num(fc, "calc_deficit_total_with_secondary_ha") - num(fc, "rl_adj_deficit_with_secondary_ha") - num(fc, "app_restore_ha")).abs().max())
    return checks


def zero_municipality_count(fc: pd.DataFrame) -> int:
    cols = [c for c in ["mun_geocodigo", "mun_geocodigo_norm"] if c in fc.columns]
    return int(
        sum(
            fc[col].astype("string").str.replace(r"\D", "", regex=True).str.fullmatch(r"0+").fillna(False).sum()
            for col in cols
        )
    )


def invalid_municipality_count(fc: pd.DataFrame) -> int:
    """Mato Grosso IBGE municipality codes all start with '51'. A non-zero
    code that does not is not a missing value (zero_municipality_count) but a
    wrong one - e.g. digits accidentally extracted from an unrelated
    composite field. See derive_municipality_code() field-priority ordering
    in code/preprocess/_10_preprocess_proxy.py."""
    cols = [c for c in ["mun_geocodigo", "mun_geocodigo_norm"] if c in fc.columns]
    count = 0
    for col in cols:
        digits = fc[col].astype("string").str.replace(r"\D", "", regex=True)
        is_zero = digits.str.fullmatch(r"0*").fillna(True)
        is_valid_mt = digits.str.startswith("51")
        count += int((~is_zero & ~is_valid_mt).sum())
    return count


def radam_zero_coverage_count(fc: pd.DataFrame) -> int:
    """Properties with positive area but radam_total_ha <= 0 have no RADAM
    vegetation classification at all - a join-coverage gap against the
    precomputed RADAM x CAR_ATP intersection, not a real all-unclassified
    property. See qa/method_alignment_*.md for the fix history."""
    if "radam_total_ha" not in fc.columns or "area_ha_car" not in fc.columns:
        return 0
    return int(((num(fc, "radam_total_ha") <= 0) & (num(fc, "area_ha_car") > 0)).sum())


def method_ok(checks: dict[str, object]) -> bool:
    return (
        checks["priority_order"] == SOURCE_ORDER
        and max(v for k, v in checks.items() if k.endswith("_max_diff")) <= 1e-6
        and checks["negative_core_cells"] == 0
    )
