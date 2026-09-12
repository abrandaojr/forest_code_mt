from __future__ import annotations

import importlib.util
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

import _00_paths as paths
import _10_kernel as kernel
import _12_gta_supply_chain as gta_chain

SCRIPT_DIR = Path(__file__).resolve().parent
paths.set_env()
ROOT = paths.ROOT
OUT_DIR = paths.TABLES
GTA_CSV = Path(os.environ.get("FCM_GTA_CSV", paths.GTA_CSV))
OUT_DIR.mkdir(parents=True, exist_ok=True)


spec = importlib.util.spec_from_file_location("fc_priority", SCRIPT_DIR / "_20_build_priority.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load _20_build_priority.py")
fc_priority = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fc_priority)


INPUT_ORDER = kernel.SOURCE_ORDER


def apply_input_order(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "input_file_type" in out.columns:
        out["input_file_type"] = pd.Categorical(
            out["input_file_type"].astype(str),
            categories=INPUT_ORDER,
            ordered=True,
        )
    return out


def ordered_input_counts(series: pd.Series) -> pd.Series:
    return series.astype(str).value_counts().reindex(INPUT_ORDER, fill_value=0)


def load_fc_consolidated() -> tuple[pd.DataFrame, dict[str, Path]]:
    parquet_path = OUT_DIR / f"forest_code_mt_priority_consolidated_{kernel.DATE}.parquet"
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        if {"cons_area_2000", "app_cap_ha"}.issubset(df.columns):
            return df, {"parquet": parquet_path}
    outputs = fc_priority.main()
    return pd.read_parquet(outputs["parquet"]), outputs


def build_final_workbook() -> dict[str, Path]:
    fc_df, fc_outputs = load_fc_consolidated()
    suppliers = gta_chain.classify_gta(GTA_CSV)

    fc_df = apply_input_order(fc_df)
    fc_df["join_key"] = gta_chain.norm_code(fc_df["property_code"])
    fc_df = fc_df.sort_values(["input_file_type", "priority_key"], kind="stable").reset_index(drop=True)
    joined = fc_df.merge(suppliers, on="join_key", how="inner", suffixes=("", "_gta"))
    joined = apply_input_order(joined)
    joined["supplier_type"] = pd.Categorical(joined["supplier_type"], gta_chain.TYPE_ORDER, ordered=True)
    joined = joined.sort_values(["input_file_type", "supplier_type", "priority_key"], kind="stable").reset_index(drop=True)

    final_xlsx = OUT_DIR / f"forest_code_gta_final_mt_{kernel.DATE}.xlsx"
    try:
        if final_xlsx.exists():
            with final_xlsx.open("a+b"):
                pass
    except PermissionError:
        stamp = datetime.now().strftime("%H%M%S")
        final_xlsx = OUT_DIR / f"forest_code_gta_final_mt_{kernel.DATE}_{stamp}.xlsx"
    final_parquet = OUT_DIR / f"forest_code_gta_final_mt_{kernel.DATE}.parquet"
    suppliers_csv = OUT_DIR / f"gta_supplier_binary_classification_{kernel.DATE}.csv"

    joined.to_parquet(final_parquet, index=False)
    suppliers.to_csv(suppliers_csv, index=False)

    counts = ordered_input_counts(fc_df["input_file_type"]).reset_index()
    counts.columns = ["input_file_type", "selected_rows_after_priority"]
    fc_tables = fc_priority.make_final_tables(fc_df, counts)

    supplier_overview = gta_chain.supplier_overview(suppliers)
    supplier_subgroups = gta_chain.supplier_subgroups(suppliers)

    fc_gta_source = gta_chain.summary_by_supplier(joined, ["input_file_type", "supplier_type"], INPUT_ORDER)
    fc_gta_size = gta_chain.summary_by_supplier(joined, ["input_file_type", "supplier_type", "size_class"], INPUT_ORDER)
    fc_gta_overall = gta_chain.summary_by_supplier(joined.assign(group="all_sources"), ["group", "supplier_type"], INPUT_ORDER)

    raw_cols = [
        "input_file_type", "property_code", "PROPERTY_ID", "supplier_type",
        "supplier_macro", "supplier_subgroup", "direct_slaughter_gt50",
        "total_cattle_moved", "slaughter_or_export_cattle", "cattle_class",
        "NOMESPROPR", "NOMEPROPRI", "SITUACAO", "MUNICIPIO_", "mun_geocodigo",
        "size_class", "area_ha_car", "rl_adj_deficit_ha", "rl_gross_deficit_ha",
        "rl_restore_ha", "rl_compensate_ha", "app_gross_deficit_ha",
        "app_restore_ha", "calc_gross_deficit_total_ha", "calc_deficit_total_ha",
    ]
    raw_cols = [c for c in raw_cols if c in joined.columns]

    with pd.ExcelWriter(final_xlsx, engine="openpyxl") as writer:
        pd.DataFrame({
            "item": [
                "description", "priority_order", "gta_direct_rule",
                "export_columns_used", "fc_rows_after_priority", "gta_supplier_rows",
                "fc_gta_matched_rows", "fc_consolidated_parquet", "joined_parquet",
                "gta_supplier_csv",
            ],
            "value": [
                "Final Forest Code and GTA product for Mato Grosso.",
                "1 SIMCAR validated; 2 SIMCAR digital; 3 SIMCAR proxy",
                "Direct supplier if at least one head was sold for slaughter or export.",
                suppliers["export_columns_used"].iloc[0] if len(suppliers) else "(none)",
                len(fc_df), len(suppliers), len(joined),
                str(fc_outputs.get("parquet", "")), str(final_parquet), str(suppliers_csv),
            ],
        }).to_excel(writer, sheet_name="README", index=False)

        for name, table in fc_tables.items():
            table.to_excel(writer, sheet_name=name[:31], index=False)
        supplier_overview.to_excel(writer, sheet_name="gta_supplier_overview", index=False)
        supplier_subgroups.to_excel(writer, sheet_name="gta_supplier_subgroups", index=False)
        suppliers.to_excel(writer, sheet_name="gta_suppliers_raw", index=False)
        fc_gta_overall.to_excel(writer, sheet_name="fc_gta_overall", index=False)
        fc_gta_source.to_excel(writer, sheet_name="fc_gta_by_source", index=False)
        fc_gta_size.to_excel(writer, sheet_name="fc_gta_by_size", index=False)
        joined[raw_cols].to_excel(writer, sheet_name="fc_gta_joined_raw", index=False)

    print("FC rows after priority:", len(fc_df))
    print("GTA supplier rows:", len(suppliers))
    print("FC x GTA matched rows:", len(joined))
    print("Rows by FC input:")
    print(ordered_input_counts(fc_df["input_file_type"]).to_string())
    print("Rows by supplier type:")
    print(suppliers["supplier_type"].value_counts().to_string())
    print("final_xlsx:", final_xlsx)
    print("final_parquet:", final_parquet)
    return {"excel": final_xlsx, "parquet": final_parquet, "suppliers_csv": suppliers_csv}


if __name__ == "__main__":
    build_final_workbook()

