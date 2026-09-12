from __future__ import annotations

import numpy as np
import pandas as pd


TYPE_ORDER = ["Direct supplier", "Indirect supplier - Tier 1", "Indirect supplier - Tier 2+"]
SUBGROUP_ORDER = ["Direct pure", "Direct also Tier 1", "Tier 1 pure", "Tier 2+"]


def num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def norm_code(s: pd.Series) -> pd.Series:
    return s.astype("string").str.upper().str.strip()


def cattle_class(total: pd.Series) -> pd.Categorical:
    return pd.cut(
        total,
        bins=[0, 1, 5, 10, 50, 100, 500, 1000, np.inf],
        labels=["= 1", "1-5", "5-10", "10-50", "50-100", "100-500", "500-1,000", "> 1,000"],
        right=True,
        include_lowest=True,
    )


def classify_gta(gta_csv) -> pd.DataFrame:
    df = pd.read_csv(gta_csv)
    export_cols = [c for c in df.columns if "export" in c.lower() and "cattle" in c.lower()]
    slaughter_cols = ["NumCattleToFederalSlh", "NumCattleToStateSlh", "NumCattleToOtherSlh"]
    cattle_cols = ["TotalCattle", "DirectCattle", "T1Cattle", "T2PlusCattle", *slaughter_cols, *export_cols]
    for col in cattle_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    grouped = (
        df.assign(PROPERTY_ID=df["SICAR"].astype("string"))
        .query("TotalCattle > 0")
        .groupby("PROPERTY_ID", dropna=False)
        .agg(
            total_cattle_moved=("TotalCattle", "sum"),
            total_direct_cattle=("DirectCattle", "sum") if "DirectCattle" in df.columns else ("TotalCattle", "sum"),
            total_t1_cattle=("T1Cattle", "sum"),
            total_t2_cattle=("T2PlusCattle", "sum"),
            total_federal_slaughter=("NumCattleToFederalSlh", "sum"),
            total_state_slaughter=("NumCattleToStateSlh", "sum"),
            total_other_slaughter=("NumCattleToOtherSlh", "sum"),
        )
        .reset_index()
    )

    if export_cols:
        export_sum = (
            df.assign(PROPERTY_ID=df["SICAR"].astype("string"))
            .groupby("PROPERTY_ID", dropna=False)[export_cols]
            .sum()
            .sum(axis=1)
            .rename("total_export_cattle")
            .reset_index()
        )
        grouped = grouped.merge(export_sum, on="PROPERTY_ID", how="left")
    else:
        grouped["total_export_cattle"] = 0.0

    grouped["total_cattle_slaughter"] = grouped["total_federal_slaughter"] + grouped["total_state_slaughter"] + grouped["total_other_slaughter"]
    grouped["slaughter_or_export_cattle"] = grouped["total_cattle_slaughter"] + grouped["total_export_cattle"]
    grouped["slaughter_ratio"] = grouped["total_cattle_slaughter"] / grouped["total_cattle_moved"].replace(0, np.nan)
    grouped["slaughter_or_export_ratio"] = grouped["slaughter_or_export_cattle"] / grouped["total_cattle_moved"].replace(0, np.nan)
    grouped["t1_ratio"] = grouped["total_t1_cattle"] / grouped["total_cattle_moved"].replace(0, np.nan)
    grouped["t2_ratio"] = grouped["total_t2_cattle"] / grouped["total_cattle_moved"].replace(0, np.nan)

    grouped["supplier_type"] = np.select(
        [
            grouped["slaughter_or_export_cattle"] > 0,
            (grouped["slaughter_or_export_cattle"] == 0) & (grouped["total_t1_cattle"] > 0),
        ],
        ["Direct supplier", "Indirect supplier - Tier 1"],
        default="Indirect supplier - Tier 2+",
    )
    grouped["supplier_type_binary_rule"] = grouped["supplier_type"]
    grouped["supplier_macro"] = grouped["supplier_type"]
    grouped["supplier_subgroup"] = np.select(
        [
            (grouped["slaughter_or_export_cattle"] > 0) & (grouped["total_t1_cattle"] > 0),
            grouped["slaughter_or_export_cattle"] > 0,
            (grouped["slaughter_or_export_cattle"] == 0) & (grouped["total_t1_cattle"] > 0),
        ],
        ["Direct also Tier 1", "Direct pure", "Tier 1 pure"],
        default="Tier 2+",
    )
    grouped["direct_slaughter_export_gt50"] = (
        grouped["supplier_type"].eq("Direct supplier") &
        (grouped["slaughter_or_export_ratio"] > 0.5)
    )
    grouped["direct_slaughter_gt50"] = grouped["direct_slaughter_export_gt50"]
    grouped["cattle_class"] = cattle_class(grouped["total_cattle_moved"])
    grouped["join_key"] = norm_code(grouped["PROPERTY_ID"])
    grouped["export_columns_used"] = ", ".join(export_cols) if export_cols else "(none found in GTA file)"
    return grouped


def supplier_overview(suppliers: pd.DataFrame) -> pd.DataFrame:
    out = (
        suppliers.groupby("supplier_type", dropna=False)
        .agg(
            n_properties=("PROPERTY_ID", "size"),
            total_cattle_head=("total_cattle_moved", "sum"),
            slaughter_or_export_head=("slaughter_or_export_cattle", "sum"),
            mean_cattle_property=("total_cattle_moved", "mean"),
        )
        .reset_index()
    )
    out["supplier_type"] = pd.Categorical(out["supplier_type"], TYPE_ORDER, ordered=True)
    return out.sort_values("supplier_type")


def supplier_subgroups(suppliers: pd.DataFrame) -> pd.DataFrame:
    out = (
        suppliers.groupby(["supplier_macro", "supplier_subgroup"], dropna=False)
        .agg(
            n_properties=("PROPERTY_ID", "size"),
            total_cattle_head=("total_cattle_moved", "sum"),
            slaughter_head=("total_cattle_slaughter", "sum"),
            slaughter_or_export_head=("slaughter_or_export_cattle", "sum"),
            direct_gt50_slaughter_export_properties=("direct_slaughter_export_gt50", "sum"),
        )
        .reset_index()
    )
    out["supplier_macro"] = pd.Categorical(out["supplier_macro"], TYPE_ORDER, ordered=True)
    out["supplier_subgroup"] = pd.Categorical(out["supplier_subgroup"], SUBGROUP_ORDER, ordered=True)
    return out.sort_values(["supplier_macro", "supplier_subgroup"])


def summary_by_supplier(df: pd.DataFrame, group_cols: list[str], source_order: list[str]) -> pd.DataFrame:
    work = df.copy()
    if "input_file_type" in work.columns:
        work["input_file_type"] = pd.Categorical(work["input_file_type"].astype(str), source_order, ordered=True)
    if "supplier_type" in work.columns:
        work["supplier_type"] = pd.Categorical(work["supplier_type"], TYPE_ORDER, ordered=True)
    for col in [
        "area_ha_car", "rl_adj_deficit_ha", "rl_gross_deficit_ha",
        "rl_surplus_total_ha", "rl_restore_ha", "rl_compensate_ha",
        "app_gross_deficit_ha", "app_restore_ha", "calc_deficit_total_ha",
        "calc_gross_deficit_total_ha", "total_cattle_moved",
        "slaughter_or_export_cattle",
    ]:
        work[col] = num(work, col)
    out = (
        work.groupby(group_cols, dropna=False, observed=False)
        .agg(
            n_properties=("priority_key", "size"),
            total_area_ha=("area_ha_car", "sum"),
            total_cattle_head=("total_cattle_moved", "sum"),
            slaughter_or_export_head=("slaughter_or_export_cattle", "sum"),
            rl_adjusted_deficit_ha=("rl_adj_deficit_ha", "sum"),
            rl_gross_deficit_ha=("rl_gross_deficit_ha", "sum"),
            app_gross_deficit_ha=("app_gross_deficit_ha", "sum"),
            gross_deficit_total_ha=("calc_gross_deficit_total_ha", "sum"),
            total_deficit_ha=("calc_deficit_total_ha", "sum"),
            rl_restore_ha=("rl_restore_ha", "sum"),
            rl_compensate_ha=("rl_compensate_ha", "sum"),
            app_restore_ha=("app_restore_ha", "sum"),
            pct_any_deficit=("calc_deficit_total_ha", lambda s: round(float((pd.to_numeric(s, errors="coerce").fillna(0) > 0).mean() * 100), 1)),
        )
        .reset_index()
    )
    sort_cols = [c for c in ["input_file_type", "supplier_type", "size_class"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, kind="stable").reset_index(drop=True)
    return out
