from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_RULES = {
    "rl_forest_pct": 0.80,
    "rl_cerrado_pct": 0.35,
    "rl_forest_pre2000": 0.50,
    "rl_cerrado_pre2000": 0.20,
    "rl_mt_forest_pct": 0.50,
}

DEFAULT_MT_SPECIAL = ["5100359", "5100805", "5103304", "5105150", "5106315", "5107958"]


def col_or_zero(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0)
    return pd.Series(0.0, index=df.index)


def sum_cols(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    if not cols:
        return pd.Series(0.0, index=df.index)
    return df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)


# Columns matching radam_*_ha that are derived metrics, not raw pivoted-FITOECOLOG
# inputs. Both this function and other pipeline stages that run before it can leave
# these on `df` (e.g. a re-run, or the ARL/nveg24 allocation step); they must never
# be treated as "unclassified raw area" or the unclassified total is wildly inflated
# by re-summing already-aggregated hectares.
DERIVED_RADAM_METRIC_NAMES = {
    "radam_forest_ha", "radam_cerrado_ha", "radam_total_ha",
    "radam_forest_nveg24_ha", "radam_cerrado_nveg24_ha", "radam_total_nveg24_ha",
}


def compute_forest_code_metrics(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rules = config.get("rules", DEFAULT_RULES)
    radam_cols = [c for c in df.columns if c.startswith("radam_") and c.endswith("_ha")]
    nveg_cols = [c for c in df.columns if c.startswith("nveg_") and c.endswith("_ha")]
    # Exact match on the pivoted FITOECOLOG label (radam_<LABEL>_ha), not substring:
    # a substring check would double-count any future compound/ecotone category whose
    # name contains both "FLORESTA" and "CERRADO" into both totals at once.
    radam_forest_col = [c for c in radam_cols if c == f"radam_{config['forest_label']}_ha"]
    radam_cerrado_col = [c for c in radam_cols if c == f"radam_{config['cerrado_label']}_ha"]
    radam_unclassified_col = [
        c for c in radam_cols
        if c not in radam_forest_col and c not in radam_cerrado_col and c not in DERIVED_RADAM_METRIC_NAMES
    ]

    df = df.copy()
    df["art67_small_prop"] = pd.to_numeric(df.get("MODULOS_FI", 0), errors="coerce").fillna(0) <= 4
    df["mt_special_mun"] = df.get("mun_geocodigo", "").astype(str).isin(config.get("mt_special", DEFAULT_MT_SPECIAL))

    df["radam_forest_ha_raw"] = sum_cols(df, radam_forest_col)
    df["radam_cerrado_ha_raw"] = sum_cols(df, radam_cerrado_col)
    # RADAM intersection slivers with a blank or null FITOECOLOG value (GIS topology
    # artifacts) are neither forest nor cerrado and are excluded from the RL basis by
    # design; surfaced here (rather than silently dropped) so affected properties are
    # auditable. See qa/ audit findings for magnitude and affected-property review.
    df["radam_unclassified_ha_raw"] = sum_cols(df, radam_unclassified_col)
    df["radam_unclassified_flag"] = df["radam_unclassified_ha_raw"] > 0
    df["radam_total_raw"] = df["radam_forest_ha_raw"] + df["radam_cerrado_ha_raw"]
    df["radam_scale"] = np.where(
        (df["radam_total_raw"] > df["area_ha_car"]) & (df["radam_total_raw"] > 0),
        df["area_ha_car"] / df["radam_total_raw"],
        1.0,
    )
    df["radam_forest_ha"] = df["radam_forest_ha_raw"] * df["radam_scale"]
    df["radam_cerrado_ha"] = df["radam_cerrado_ha_raw"] * df["radam_scale"]
    df["radam_total_ha"] = df["radam_forest_ha"] + df["radam_cerrado_ha"]

    df["avail_ha"] = np.maximum(df["area_ha_car"] - col_or_zero(df, "cons_area_2000"), 0)

    df["rl_req_uncapped_forest_ha"] = df["radam_forest_ha"] * rules["rl_forest_pct"]
    df["rl_req_uncapped_cerrado_ha"] = df["radam_cerrado_ha"] * rules["rl_cerrado_pct"]
    df["rl_req_uncapped_total_ha"] = df["rl_req_uncapped_forest_ha"] + df["rl_req_uncapped_cerrado_ha"]
    df["rl_cap_ha"] = np.minimum(df["rl_req_uncapped_total_ha"], df["avail_ha"])
    total_req = df["rl_req_uncapped_total_ha"].replace(0, np.nan)
    df["rl_req_forest_ha"] = np.where(total_req.notna(), df["rl_cap_ha"] * df["rl_req_uncapped_forest_ha"] / total_req, 0)
    df["rl_req_cerrado_ha"] = np.where(total_req.notna(), df["rl_cap_ha"] * df["rl_req_uncapped_cerrado_ha"] / total_req, 0)
    df["rl_req_total_ha"] = df["rl_req_forest_ha"] + df["rl_req_cerrado_ha"]

    df["rl_req_pre2000_uncapped_f"] = df["radam_forest_ha"] * rules["rl_forest_pre2000"]
    df["rl_req_pre2000_uncapped_c"] = df["radam_cerrado_ha"] * rules["rl_cerrado_pre2000"]
    df["rl_req_pre2000_total_unc"] = df["rl_req_pre2000_uncapped_f"] + df["rl_req_pre2000_uncapped_c"]
    pre_total = df["rl_req_pre2000_total_unc"].replace(0, np.nan)
    pre_cap = np.minimum(df["rl_req_pre2000_total_unc"], df["avail_ha"])
    df["rl_req_pre2000_forest_ha"] = np.where(pre_total.notna(), pre_cap * df["rl_req_pre2000_uncapped_f"] / pre_total, 0)
    df["rl_req_pre2000_cerrado_ha"] = np.where(pre_total.notna(), pre_cap * df["rl_req_pre2000_uncapped_c"] / pre_total, 0)

    df["rl_req_mt_forest_ha"] = np.where(
        df["mt_special_mun"],
        np.minimum(df["radam_forest_ha"] * rules["rl_mt_forest_pct"], df["avail_ha"]),
        df["rl_req_forest_ha"],
    )

    df["rl_exist_forest_ha"] = col_or_zero(df, "radam_forest_nveg24_ha")
    df["rl_exist_cerrado_ha"] = col_or_zero(df, "radam_cerrado_nveg24_ha")
    df["rl_exist_total_ha"] = df["rl_exist_forest_ha"] + df["rl_exist_cerrado_ha"]
    df["rl_gross_deficit_forest_ha"] = np.maximum(df["rl_req_forest_ha"] - df["rl_exist_forest_ha"], 0)
    df["rl_gross_deficit_cerrado_ha"] = np.maximum(df["rl_req_cerrado_ha"] - df["rl_exist_cerrado_ha"], 0)
    df["rl_gross_deficit_ha"] = df["rl_gross_deficit_forest_ha"] + df["rl_gross_deficit_cerrado_ha"]
    df["rl_surplus_forest_ha"] = np.maximum(df["rl_exist_forest_ha"] - df["rl_req_forest_ha"], 0)
    df["rl_surplus_cerrado_ha"] = np.maximum(df["rl_exist_cerrado_ha"] - df["rl_req_cerrado_ha"], 0)
    df["rl_surplus_total_ha"] = df["rl_surplus_forest_ha"] + df["rl_surplus_cerrado_ha"]

    df["art68_exempt_forest"] = (df["rl_exist_forest_ha"] >= df["rl_req_pre2000_forest_ha"]) & (df["radam_forest_ha"] > 0)
    df["art68_exempt_cerrado"] = (df["rl_exist_cerrado_ha"] >= df["rl_req_pre2000_cerrado_ha"]) & (df["radam_cerrado_ha"] > 0)
    df["rl_adj_deficit_forest_ha"] = np.select(
        [df["art67_small_prop"], df["art68_exempt_forest"], df["mt_special_mun"]],
        [0, np.maximum(df["rl_req_pre2000_forest_ha"] - df["rl_exist_forest_ha"], 0), np.maximum(df["rl_req_mt_forest_ha"] - df["rl_exist_forest_ha"], 0)],
        default=np.maximum(df["rl_req_forest_ha"] - df["rl_exist_forest_ha"], 0),
    )
    df["rl_adj_deficit_cerrado_ha"] = np.select(
        [df["art67_small_prop"], df["art68_exempt_cerrado"]],
        [0, np.maximum(df["rl_req_pre2000_cerrado_ha"] - df["rl_exist_cerrado_ha"], 0)],
        default=np.maximum(df["rl_req_cerrado_ha"] - df["rl_exist_cerrado_ha"], 0),
    )
    df["rl_adj_deficit_ha"] = df["rl_adj_deficit_forest_ha"] + df["rl_adj_deficit_cerrado_ha"]
    df["rl_post2008_ha"] = np.minimum(col_or_zero(df, "auas_post2008"), df["avail_ha"])
    df["rl_restore_ha"] = np.minimum(df["rl_post2008_ha"], df["rl_adj_deficit_ha"])
    df["rl_compensate_ha"] = np.maximum(df["rl_adj_deficit_ha"] - df["rl_restore_ha"], 0)

    df["app_req_ha"] = col_or_zero(df, "app")
    df["app_preserved_ha"] = col_or_zero(df, "app_fnl_avn24")
    df["app_gross_deficit_ha"] = np.maximum(df["app_req_ha"] - df["app_preserved_ha"], 0)
    mf = pd.to_numeric(df.get("MODULOS_FI", 0), errors="coerce")
    df["app_replant_raw_ha"] = np.select(
        [mf.isna(), mf <= 1, (mf > 1) & (mf <= 2), (mf > 2) & (mf <= 4), (mf > 4) & (mf <= 10), mf > 10],
        [0, col_or_zero(df, "appd_lte1mf_cs08"), col_or_zero(df, "appd_1a2mf_cs08"), col_or_zero(df, "appd_2a4mf_cs08"), col_or_zero(df, "appd_4a10mf_cs08"), col_or_zero(df, "appd_gt10mf_cs08")],
        default=0,
    )
    df["app_cap_ha"] = np.select([mf.isna(), mf <= 2, (mf > 2) & (mf <= 4)], [np.inf, 0.10 * df["area_ha_car"], 0.20 * df["area_ha_car"]], default=np.inf)
    df["app_restore_auas_ha"] = col_or_zero(df, "app_fnl_auas")
    df["app_consolidated_ha"] = col_or_zero(df, "app_fnl_cs08")
    df["app_consol_restore_ha"] = np.minimum.reduce([df["app_replant_raw_ha"], df["app_consolidated_ha"], df["app_gross_deficit_ha"]])
    df["app_restore_ha"] = np.minimum.reduce([df["app_consol_restore_ha"] + df["app_restore_auas_ha"], df["app_gross_deficit_ha"], df["app_cap_ha"]])
    return df


def add_secondary_vegetation_scenarios(df: pd.DataFrame, secondary: pd.DataFrame) -> pd.DataFrame:
    stale_cols = [
        c for c in df.columns
        if c == "secondary_vegetation_ha" or c.endswith("_with_secondary_ha") or c in {
            "secondary_deficit_reduction_ha",
            "compliant_baseline",
            "compliant_with_secondary",
            "secondary_changes_to_compliant",
        }
    ]
    out = df.drop(columns=stale_cols, errors="ignore").merge(secondary, on="priority_key", how="left")
    out["secondary_vegetation_ha"] = col_or_zero(out, "secondary_vegetation_ha").clip(lower=0)
    out["rl_exist_forest_with_secondary_ha"] = col_or_zero(out, "rl_exist_forest_ha") + out["secondary_vegetation_ha"]
    out["rl_gross_deficit_forest_with_secondary_ha"] = (col_or_zero(out, "rl_req_forest_ha") - out["rl_exist_forest_with_secondary_ha"]).clip(lower=0)
    out["rl_surplus_forest_with_secondary_ha"] = (out["rl_exist_forest_with_secondary_ha"] - col_or_zero(out, "rl_req_forest_ha")).clip(lower=0)
    out["rl_gross_deficit_with_secondary_ha"] = out["rl_gross_deficit_forest_with_secondary_ha"] + col_or_zero(out, "rl_gross_deficit_cerrado_ha")
    out["rl_surplus_with_secondary_ha"] = out["rl_surplus_forest_with_secondary_ha"] + col_or_zero(out, "rl_surplus_cerrado_ha")

    art68_f = (out["rl_exist_forest_with_secondary_ha"] >= col_or_zero(out, "rl_req_pre2000_forest_ha")) & (col_or_zero(out, "radam_forest_ha") > 0)
    small = out["art67_small_prop"].astype(bool)
    mt_special = out["mt_special_mun"].astype(bool)
    out["rl_adj_deficit_forest_with_secondary_ha"] = np.select(
        [small, art68_f, mt_special],
        [0, 0, (col_or_zero(out, "rl_req_mt_forest_ha") - out["rl_exist_forest_with_secondary_ha"]).clip(lower=0)],
        default=out["rl_gross_deficit_forest_with_secondary_ha"],
    )
    out["rl_adj_deficit_cerrado_with_secondary_ha"] = col_or_zero(out, "rl_adj_deficit_cerrado_ha")
    out["rl_adj_deficit_with_secondary_ha"] = out["rl_adj_deficit_forest_with_secondary_ha"] + out["rl_adj_deficit_cerrado_with_secondary_ha"]
    out["rl_restore_with_secondary_ha"] = np.minimum(out["rl_adj_deficit_with_secondary_ha"], col_or_zero(out, "rl_post2008_ha"))
    out["rl_compensate_with_secondary_ha"] = (out["rl_adj_deficit_with_secondary_ha"] - out["rl_restore_with_secondary_ha"]).clip(lower=0)
    out["calc_gross_deficit_total_with_secondary_ha"] = out["rl_adj_deficit_with_secondary_ha"] + col_or_zero(out, "app_gross_deficit_ha")
    out["calc_deficit_total_with_secondary_ha"] = out["rl_adj_deficit_with_secondary_ha"] + col_or_zero(out, "app_restore_ha")
    out["secondary_deficit_reduction_ha"] = (col_or_zero(out, "calc_deficit_total_ha") - out["calc_deficit_total_with_secondary_ha"]).clip(lower=0)
    out["compliant_baseline"] = col_or_zero(out, "calc_deficit_total_ha").le(0)
    out["compliant_with_secondary"] = out["calc_deficit_total_with_secondary_ha"].le(0)
    out["secondary_changes_to_compliant"] = (~out["compliant_baseline"]) & out["compliant_with_secondary"]
    return out


def add_cons2000_scenarios(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    total_req = (
        col_or_zero(out, "rl_req_uncapped_total_ha")
        if "rl_req_uncapped_total_ha" in out.columns
        else col_or_zero(out, "radam_forest_ha") * DEFAULT_RULES["rl_forest_pct"] + col_or_zero(out, "radam_cerrado_ha") * DEFAULT_RULES["rl_cerrado_pct"]
    )
    req_forest_unc = (
        col_or_zero(out, "rl_req_uncapped_forest_ha")
        if "rl_req_uncapped_forest_ha" in out.columns
        else col_or_zero(out, "radam_forest_ha") * DEFAULT_RULES["rl_forest_pct"]
    )
    req_cerrado_unc = (
        col_or_zero(out, "rl_req_uncapped_cerrado_ha")
        if "rl_req_uncapped_cerrado_ha" in out.columns
        else col_or_zero(out, "radam_cerrado_ha") * DEFAULT_RULES["rl_cerrado_pct"]
    )
    total_req_nonzero = total_req.replace(0, np.nan)
    avail_without = col_or_zero(out, "area_ha_car")
    cap_without = np.minimum(total_req, avail_without)
    out["rl_req_total_without_cons2000_ha"] = cap_without
    out["rl_req_forest_without_cons2000_ha"] = np.where(total_req_nonzero.notna(), cap_without * req_forest_unc / total_req_nonzero, 0)
    out["rl_req_cerrado_without_cons2000_ha"] = np.where(total_req_nonzero.notna(), cap_without * req_cerrado_unc / total_req_nonzero, 0)

    pre_unc_f = col_or_zero(out, "radam_forest_ha") * DEFAULT_RULES["rl_forest_pre2000"]
    pre_unc_c = col_or_zero(out, "radam_cerrado_ha") * DEFAULT_RULES["rl_cerrado_pre2000"]
    pre_total = (pre_unc_f + pre_unc_c).replace(0, np.nan)
    pre_cap = np.minimum(pre_unc_f + pre_unc_c, avail_without)
    pre_f = np.where(pre_total.notna(), pre_cap * pre_unc_f / pre_total, 0)
    pre_c = np.where(pre_total.notna(), pre_cap * pre_unc_c / pre_total, 0)
    mt_f = np.where(out["mt_special_mun"].astype(bool), np.minimum(col_or_zero(out, "radam_forest_ha") * DEFAULT_RULES["rl_mt_forest_pct"], avail_without), out["rl_req_forest_without_cons2000_ha"])

    exist_f = col_or_zero(out, "rl_exist_forest_ha")
    exist_c = col_or_zero(out, "rl_exist_cerrado_ha")
    art68_f = (exist_f >= pre_f) & (col_or_zero(out, "radam_forest_ha") > 0)
    art68_c = (exist_c >= pre_c) & (col_or_zero(out, "radam_cerrado_ha") > 0)
    small = out["art67_small_prop"].astype(bool)
    mt_special = out["mt_special_mun"].astype(bool)
    out["rl_adj_deficit_forest_without_cons2000_ha"] = np.select(
        [small, art68_f, mt_special],
        [0, np.maximum(pre_f - exist_f, 0), np.maximum(mt_f - exist_f, 0)],
        default=np.maximum(out["rl_req_forest_without_cons2000_ha"] - exist_f, 0),
    )
    out["rl_adj_deficit_cerrado_without_cons2000_ha"] = np.select(
        [small, art68_c],
        [0, np.maximum(pre_c - exist_c, 0)],
        default=np.maximum(out["rl_req_cerrado_without_cons2000_ha"] - exist_c, 0),
    )
    out["rl_adj_deficit_without_cons2000_ha"] = out["rl_adj_deficit_forest_without_cons2000_ha"] + out["rl_adj_deficit_cerrado_without_cons2000_ha"]
    post2008 = col_or_zero(out, "auas_post2008")
    if (post2008 == 0).all():
        post2008 = col_or_zero(out, "rl_post2008_ha")
    out["rl_restore_without_cons2000_ha"] = np.minimum(np.minimum(post2008, avail_without), out["rl_adj_deficit_without_cons2000_ha"])
    out["rl_compensate_without_cons2000_ha"] = np.maximum(out["rl_adj_deficit_without_cons2000_ha"] - out["rl_restore_without_cons2000_ha"], 0)

    out["app_restore_without_cons2000_ha"] = col_or_zero(out, "app_restore_ha")
    out["combined_with_cons2000_ha"] = col_or_zero(out, "rl_adj_deficit_ha") + col_or_zero(out, "app_restore_ha")
    out["combined_without_cons2000_ha"] = out["rl_adj_deficit_without_cons2000_ha"] + out["app_restore_without_cons2000_ha"]
    out["rl_cons2000_delta_ha"] = out["rl_adj_deficit_without_cons2000_ha"] - col_or_zero(out, "rl_adj_deficit_ha")
    out["app_cons2000_delta_ha"] = out["app_restore_without_cons2000_ha"] - col_or_zero(out, "app_restore_ha")
    out["combined_cons2000_delta_ha"] = out["combined_without_cons2000_ha"] - out["combined_with_cons2000_ha"]
    out["compliant_with_cons2000"] = out["combined_with_cons2000_ha"] <= 0
    out["compliant_without_cons2000"] = out["combined_without_cons2000_ha"] <= 0
    return out
