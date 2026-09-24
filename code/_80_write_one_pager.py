from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from PIL import Image, ImageDraw, ImageFont

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import _00_paths as paths

paths.set_env()
ROOT = paths.ROOT
OUT_DIR = paths.TABLES
REPORT_DIR = paths.REPORTS
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TODAY = paths.RUN_DATE
MAP_WORK_DIR = REPORT_DIR / "_tmp_one_pager_maps"
MAP_WORK_DIR.mkdir(parents=True, exist_ok=True)
PAPER_FIG_DIR = paths.FIGURES
PAPER_FIG_DIR.mkdir(parents=True, exist_ok=True)

PNG_PATH = REPORT_DIR / f"forest_code_mt_one_pager_diagnostic_{TODAY}.png"
PNG_PT_PATH = REPORT_DIR / f"diagnostico_codigo_florestal_mt_one_pager_{TODAY}.png"
MAP_COUNT_PATH = MAP_WORK_DIR / f"one_pager_map_noncompliant_properties_{TODAY}.png"
MAP_HECTARES_PATH = MAP_WORK_DIR / f"one_pager_map_noncompliance_hectares_{TODAY}.png"
MAP_APP_PATH = MAP_WORK_DIR / f"one_pager_map_app_noncompliant_properties_{TODAY}.png"
MAP_APP_HECTARES_PATH = MAP_WORK_DIR / f"one_pager_map_app_noncompliance_hectares_per_property_{TODAY}.png"
MAP_RL_PATH = MAP_WORK_DIR / f"one_pager_map_legal_reserve_noncompliant_properties_{TODAY}.png"
MAP_RL_HECTARES_PATH = MAP_WORK_DIR / f"one_pager_map_legal_reserve_noncompliance_hectares_per_property_{TODAY}.png"
MAP_RL_WITHOUT_2000_PATH = MAP_WORK_DIR / f"one_pager_map_legal_reserve_without_2000_rule_properties_{TODAY}.png"
MAP_RL_WITHOUT_2000_HECTARES_PATH = (
    MAP_WORK_DIR / f"one_pager_map_legal_reserve_without_2000_rule_hectares_per_property_{TODAY}.png"
)
PAPER_MAP_PANEL_PATH = PAPER_FIG_DIR / "Figure_09A_municipal_noncompliance_panel_1_of_2.png"
PAPER_MAP_PANEL_2_PATH = PAPER_FIG_DIR / "Figure_09B_municipal_noncompliance_panel_2_of_2.png"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


F = {
    "title": font(58, True),
    "subtitle": font(30),
    "section": font(30, True),
    "label": font(25, True),
    "body": font(25),
    "small": font(22),
    "tiny": font(18),
    "flag": font(22, True),
}


COLORS = {
    "ink": "#1f2933",
    "muted": "#52616b",
    "line": "#c8d3dc",
    "blue": "#30383d",
    "blue_light": "#eff1f2",
    "green": "#197b55",
    "green_light": "#e9f7ef",
    "amber": "#9a5b00",
    "amber_light": "#fff4dd",
    "red": "#a33131",
    "red_light": "#fdeaea",
    "gray_light": "#f5f7fa",
    "direct_light": "#f3f4f4",
    "direct_mixed_light": "#eeeeee",
    "gt50_light": "#f5eee8",
    "tier1_light": "#e9ecee",
    "tier2_light": "#f6f6f6",
    "white": "#ffffff",
}
GRAY_SCALE = ["#F7F7F7", "#D9D9D9", "#BDBDBD", "#969696", "#636363", "#252525"]
ORANGE_SCALE = ["#F7F7F7", "#FEE6CE", "#FDAE6B", "#F16913", "#A63603", "#5A1F00"]


def fmt_num(value: float, digits: int = 0) -> str:
    return f"{value:,.{digits}f}"


def first_col(df: pd.DataFrame, *names: str) -> str:
    for name in names:
        if name in df.columns:
            return name
    raise KeyError(f"None of these columns were found: {names}")


def read_results() -> dict[str, object]:
    wb = OUT_DIR / f"masson_style_final_tables_figures_{TODAY}.xlsx"
    fc = pd.read_parquet(OUT_DIR / f"forest_code_mt_priority_consolidated_{TODAY}.parquet")
    gta = pd.read_parquet(OUT_DIR / f"forest_code_gta_final_mt_{TODAY}.parquet")
    gtable = pd.read_excel(wb, sheet_name="Table_29_Cattle_Combined")
    sec = pd.read_excel(wb, sheet_name="Table_16_SecVeg_Input")
    mun = pd.read_excel(wb, sheet_name="Table_18_Top20_Mun")
    status = pd.read_excel(wb, sheet_name="Table_02_Status")
    veg = pd.read_excel(wb, sheet_name="Table_06_Vegetation_Cover")
    lr = pd.read_excel(wb, sheet_name="Table_08_LR_Compliance")
    app = pd.read_excel(wb, sheet_name="Table_09_APP")
    combined = pd.read_excel(wb, sheet_name="Table_10_Combined_Size")
    cons = pd.read_excel(wb, sheet_name="Table_12_Cons2000_Overall")
    delta = pd.read_excel(wb, sheet_name="Table_13_Cons2000_Delta")
    special = pd.read_excel(wb, sheet_name="Table_39_Special_Areas")

    active_row = status.loc[status["Registration Status"].eq("Active")].iloc[0]
    total_row = status.loc[status["Registration Status"].eq("Total")].iloc[0]
    combined_total_col = first_col(combined, "Total affected area (hectares)", "Adj. Deficit (hectares)")
    combined_gross_col = first_col(combined, "Gross affected area (hectares)", "Gross Deficit (hectares)")
    combined_restore_col = first_col(combined, "Restoration area (hectares)", "To Restore (hectares)")
    combined_comp_col = first_col(combined, "Compensation area (hectares)", "To Compensate (hectares)")
    cattle_total_col = first_col(gtable, "Total affected area (hectares)", "Adj. Deficit (hectares)")
    cattle_restore_col = first_col(gtable, "Restoration area (hectares)", "To Restore (hectares)")
    cattle_comp_col = first_col(gtable, "Compensation area (hectares)", "To Compensate (hectares)")
    cattle_totals = gtable.groupby("Category", as_index=True)[[cattle_total_col, cattle_restore_col, cattle_comp_col]].sum()
    active_total = combined[combined_total_col].sum()
    top5 = mun.head(5)
    top20 = mun.head(20)

    active_status = ~fc["SITUACAO"].astype(str).str.upper().str.contains("CANCELADO|INDEFERIDO|REJEIT", na=False)
    active = fc.loc[active_status]
    net_residual = (
        active["calc_deficit_total_ha"]
        - active["rl_adj_deficit_ha"].fillna(0)
        - active["app_restore_ha"].fillna(0)
    ).abs().max()
    gross_residual = (
        active["calc_gross_deficit_total_ha"]
        - active["rl_gross_deficit_ha"].fillna(0)
        - active["app_gross_deficit_ha"].fillna(0)
    ).abs().max()
    zero_codes = 0
    for col in [c for c in fc.columns if "mun" in c.lower() or "geocodigo" in c.lower()]:
        s = fc[col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        zero_codes += int(s.str.fullmatch(r"0{5,7}").fillna(False).sum())

    input_counts = fc["input_file_type"].value_counts().to_dict()
    input_areas = fc.groupby("input_file_type")["AREA_HA"].sum().to_dict()
    sec_totals = sec.sum(numeric_only=True)
    cons_base = cons.loc[cons["Scenario"].isin(["With 2000 rule", "LR with 2000 rule"])].iloc[0]
    cons_without = cons.loc[cons["Scenario"].isin(["Without 2000 rule", "LR without 2000 rule"])].iloc[0]
    compliant_col = first_col(cons, "Compliant properties", "Compliant n")
    affected_col = first_col(cons, "Affected properties", "Liability n")
    total_affected_col = first_col(cons, "Total affected area (hectares)", "Total Liab. (hectares)")
    delta_total_col = first_col(delta, "Total 2000-rule effect area (hectares)", "Total delta (hectares)")
    subgroup = (
        gta.groupby("supplier_subgroup", dropna=False)
        .agg(
            properties=("property_join_key", "size"),
            liability=("calc_deficit_total_ha", "sum"),
            cattle=("total_cattle_moved", "sum"),
            slaughter_export=("slaughter_or_export_cattle", "sum"),
        )
        .to_dict("index")
    )
    gt50 = gta["direct_slaughter_gt50"].fillna(False).astype(bool)
    binary_direct = gta["slaughter_or_export_cattle"].fillna(0).gt(0)
    final_positive = active["calc_deficit_total_ha"].gt(0)
    lr_positive = active["rl_adj_deficit_ha"].fillna(0).gt(0)
    app_positive = active["app_restore_ha"].fillna(0).gt(0)
    restore_positive = (active["rl_restore_ha"].fillna(0) + active["app_restore_ha"].fillna(0)).gt(0)
    compensate_positive = active["rl_compensate_ha"].fillna(0).gt(0)
    surplus_positive = active["rl_surplus_total_ha"].fillna(0).gt(0)
    secondary_properties_col = first_col(sec, "Properties", "N")
    secondary_liability_n = int(sec_totals[secondary_properties_col] - sec_totals["With secondary compliant n"])
    large_active_n = int(active["size_class"].eq("Large (>15 MF)").sum())

    return {
        "records": int(len(fc)),
        "active_properties": int(active_row["Number of Properties"]),
        "inactive": int(total_row["Number of Properties"] - active_row["Number of Properties"]),
        "total_area_mha": float(total_row["Area (million hectares)"]),
        "active_area_mha": float(active_row["Area (million hectares)"]),
        "validated": int(input_counts.get("simcar_validado", 0)),
        "digital": int(input_counts.get("simcar_digital", 0)),
        "proxy": int(input_counts.get("simcar_proxy", 0)),
        "validated_area": float(input_areas.get("simcar_validado", 0)),
        "digital_area": float(input_areas.get("simcar_digital", 0)),
        "proxy_area": float(input_areas.get("simcar_proxy", 0)),
        "final_liability": float(active_total),
        "gross_combined": float(combined[combined_gross_col].sum()),
        "lr_required": float(lr[first_col(lr, "Required LR area (hectares)", "Required (hectares)")].sum()),
        "lr_gross": float(lr[first_col(lr, "LR gross affected area (hectares)", "Gross Deficit")].sum()),
        "lr_adjusted": float(lr[first_col(lr, "LR affected area (hectares)", "Adj. Deficit")].sum()),
        "lr_surplus": float(lr[first_col(lr, "LR surplus area (hectares)", "Surplus (hectares)")].sum()),
        "app_required": float(app["APP Required (hectares)"].sum()),
        "app_gross": float(app[first_col(app, "APP gross affected area (hectares)", "APP Gross Deficit (hectares)")].sum()),
        "app_restore": float(app[first_col(app, "APP affected area (hectares)", "APP Net Deficit (hectares)")].sum()),
        "restore": float(combined[combined_restore_col].sum()),
        "compensate": float(combined[combined_comp_col].sum()),
        "compliant": int(cons_base[compliant_col]),
        "liability_n": int(cons_base[affected_col]),
        "gross_liability_n": int((active["calc_gross_deficit_total_ha"].fillna(0) > 0).sum()),
        "lr_liability_n": int(lr_positive.sum()),
        "app_liability_n": int(app_positive.sum()),
        "restore_n": int(restore_positive.sum()),
        "compensate_n": int(compensate_positive.sum()),
        "surplus_n": int(surplus_positive.sum()),
        "compliant_pct": float(cons_base["% Compliant"]),
        "without_2000_n": int(cons_without[affected_col]),
        "without_2000": float(cons_without[total_affected_col]),
        "without_2000_delta_n": int(cons_without[affected_col] - cons_base[affected_col]),
        "without_2000_delta": float(delta[delta_total_col].iloc[0]),
        "secondary_area": float(sec_totals["Secondary veg. (hectares)"]),
        "secondary_properties": int(sec_totals["Secondary veg. n"]),
        "secondary_liability": float(sec_totals["With secondary total liab. (hectares)"]),
        "secondary_liability_n": secondary_liability_n,
        "secondary_reduction": float(sec_totals["Liab. reduction (hectares)"]),
        "newly_compliant": int(sec_totals["Newly compliant n"]),
        "large_liability": float(combined.loc[combined["Size Class"].eq("Large (>15 MF)"), combined_total_col].iloc[0]),
        "large_active_n": large_active_n,
        "large_share": float(combined.loc[combined["Size Class"].eq("Large (>15 MF)"), combined_total_col].iloc[0] / active_total * 100),
        "top5_mun": " / ".join(top5["Municipality"].astype(str).tolist()),
        "top5_properties": int(top5["Properties"].sum()),
        "top5_total": float(top5[first_col(top5, "Total affected area (hectares)", "Total Deficit")].sum()),
        "top20_properties": int(top20["Properties"].sum()),
        "top20_total": float(top20[first_col(top20, "Total affected area (hectares)", "Total Deficit")].sum()),
        "top20_share": float(top20[first_col(top20, "Total affected area (hectares)", "Total Deficit")].sum() / active_total * 100),
        "direct_liability": float(cattle_totals.loc["Direct supplier", cattle_total_col]),
        "tier1_liability": float(cattle_totals.loc["Indirect supplier - Tier 1", cattle_total_col]),
        "tier2_liability": float(cattle_totals.loc["Indirect supplier - Tier 2+", cattle_total_col]),
        "gta_liability": float(cattle_totals[cattle_total_col].sum()),
        "gta_properties": 45637,
        "direct_properties": 20316,
        "indirect_properties": 25321,
        "cattle_head": 48595833,
        "slaughter_head": 12284019,
        "supplier_subgroups": subgroup,
        "direct_gt50_n": int(gt50.sum()),
        "direct_gt50_liability": float(gta.loc[gt50, "calc_deficit_total_ha"].sum()),
        "direct_gt50_cattle": float(gta.loc[gt50, "slaughter_or_export_cattle"].sum()),
        "binary_direct_n": int(binary_direct.sum()),
        "binary_direct_liability": float(gta.loc[binary_direct, "calc_deficit_total_ha"].sum()),
        "binary_direct_cattle": float(gta.loc[binary_direct, "slaughter_or_export_cattle"].sum()),
        "forest_basis": float(veg["Forest area (hectares)"].iloc[0]),
        "cerrado_basis": float(veg["Cerrado area (hectares)"].iloc[0]),
        "native_basis": float(veg["Total native vegetation basis (hectares)"].iloc[0]),
        "special": special,
        "net_residual": float(net_residual),
        "gross_residual": float(gross_residual),
        "zero_codes": zero_codes,
    }


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt, fill=None, max_width: int | None = None, line_gap=4):
    fill = fill or COLORS["ink"]
    x, y = xy
    if max_width is None:
        draw.text((x, y), text, font=fnt, fill=fill)
        return y + draw.textbbox((x, y), text, font=fnt)[3] - y
    words = text.split()
    line = ""
    for word in words:
        test = word if not line else f"{line} {word}"
        if draw.textlength(test, font=fnt) <= max_width:
            line = test
        else:
            draw.text((x, y), line, font=fnt, fill=fill)
            y += fnt.size + line_gap
            line = word
    if line:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap
    return y


def rounded(draw, box, fill, outline=COLORS["line"], radius=18, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def flag(draw, x, y, text, tone="info"):
    fills = {"ok": COLORS["green_light"], "high": COLORS["red_light"], "info": COLORS["blue_light"], "watch": COLORS["amber_light"]}
    inks = {"ok": COLORS["green"], "high": COLORS["red"], "info": COLORS["blue"], "watch": COLORS["amber"]}
    w = int(draw.textlength(text, font=F["flag"])) + 28
    rounded(draw, (x, y, x + w, y + 34), fills[tone], fills[tone], radius=10, width=1)
    draw.text((x + 14, y + 6), text, font=F["flag"], fill=inks[tone])
    return w


def row(draw, x, y, w, label, value, unit="", ref="", tone="info", bg=None):
    if bg:
        draw.rectangle((x - 8, y, x + w + 8, y + 66), fill=bg)
    draw.line((x, y, x + w, y), fill=COLORS["line"], width=1)
    y += 8
    draw_text(draw, (x, y), label, F["body"], max_width=int(w * 0.34), line_gap=1)
    vx = x + int(w * 0.37)
    draw.text((vx, y), value, font=F["label"], fill=COLORS["ink"])
    if unit:
        draw.text((vx, y + 30), unit, font=F["tiny"], fill=COLORS["muted"])
    if ref:
        draw_text(draw, (x + int(w * 0.61), y), ref, F["small"], fill=COLORS["muted"], max_width=int(w * 0.25), line_gap=1)
    flag(draw, x + w - 86, y + 3, tone.upper(), tone)
    return y + 58


def row_pa(draw, x, y, w, label, properties, hectares, tone="info", note="", bg=None):
    prop_text = f"{fmt_num(properties)}"
    area_text = f"{fmt_num(hectares, 1)} hectares"
    ref = area_text if not note else f"{area_text}\n{note}"
    return row(draw, x, y, w, label, prop_text, "properties", ref, tone, bg=bg)


def row_record_area(draw, x, y, w, label, records, hectares, tone="info", unit="records", bg=None):
    return row(draw, x, y, w, label, fmt_num(records), unit, f"{fmt_num(hectares, 1)} hectares", tone, bg=bg)


def gauge(draw, x, y, w, pct, label, color):
    draw.text((x, y), label, font=F["small"], fill=COLORS["muted"])
    y += 28
    rounded(draw, (x, y, x + w, y + 20), COLORS["gray_light"], COLORS["gray_light"], radius=10, width=1)
    fill_w = max(4, int(w * max(0, min(pct, 100)) / 100))
    rounded(draw, (x, y, x + fill_w, y + 20), color, color, radius=10, width=1)
    draw.text((x + w + 10, y - 2), f"{pct:.1f}%", font=F["small"], fill=COLORS["ink"])
    return y + 34


def section(draw, box, title):
    x0, y0, x1, y1 = box
    rounded(draw, box, COLORS["white"])
    draw.rectangle((x0, y0, x1, y0 + 54), fill=COLORS["blue_light"])
    draw.line((x0, y0 + 54, x1, y0 + 54), fill=COLORS["line"], width=2)
    draw.text((x0 + 22, y0 + 12), title, font=F["section"], fill=COLORS["blue"])
    return x0 + 22, y0 + 70, x1 - x0 - 44


def ncol(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return pd.to_numeric(df[column], errors="coerce").fillna(0)
    return pd.Series(0, index=df.index, dtype="float64")


def add_lr_without_2000_rule(active: pd.DataFrame) -> pd.DataFrame:
    out = active.copy()
    total_req = ncol(out, "rl_req_uncapped_total_ha")
    if total_req.eq(0).all():
        total_req = ncol(out, "radam_forest_ha") * 0.80 + ncol(out, "radam_cerrado_ha") * 0.35
    req_forest_unc = ncol(out, "rl_req_uncapped_forest_ha")
    if req_forest_unc.eq(0).all():
        req_forest_unc = ncol(out, "radam_forest_ha") * 0.80
    req_cerrado_unc = ncol(out, "rl_req_uncapped_cerrado_ha")
    if req_cerrado_unc.eq(0).all():
        req_cerrado_unc = ncol(out, "radam_cerrado_ha") * 0.35

    total_req_nonzero = total_req.replace(0, np.nan)
    avail_without = ncol(out, "area_ha_car")
    cap_without = np.minimum(total_req, avail_without)
    out["rl_req_total_without_cons2000_ha"] = cap_without
    out["rl_req_forest_without_cons2000_ha"] = np.where(total_req_nonzero.notna(), cap_without * req_forest_unc / total_req_nonzero, 0)
    out["rl_req_cerrado_without_cons2000_ha"] = np.where(total_req_nonzero.notna(), cap_without * req_cerrado_unc / total_req_nonzero, 0)

    pre_unc_f = ncol(out, "radam_forest_ha") * 0.50
    pre_unc_c = ncol(out, "radam_cerrado_ha") * 0.20
    pre_total = (pre_unc_f + pre_unc_c).replace(0, np.nan)
    pre_cap = np.minimum(pre_unc_f + pre_unc_c, avail_without)
    pre_f = np.where(pre_total.notna(), pre_cap * pre_unc_f / pre_total, 0)
    pre_c = np.where(pre_total.notna(), pre_cap * pre_unc_c / pre_total, 0)
    mt_special = out["mt_special_mun"].astype(bool) if "mt_special_mun" in out.columns else pd.Series(False, index=out.index)
    mt_f = np.where(mt_special, np.minimum(ncol(out, "radam_forest_ha") * 0.50, avail_without), out["rl_req_forest_without_cons2000_ha"])

    exist_f = ncol(out, "rl_exist_forest_ha")
    exist_c = ncol(out, "rl_exist_cerrado_ha")
    art68_f = (exist_f >= pre_f) & ncol(out, "radam_forest_ha").gt(0)
    art68_c = (exist_c >= pre_c) & ncol(out, "radam_cerrado_ha").gt(0)
    small = out["art67_small_prop"].astype(bool) if "art67_small_prop" in out.columns else pd.Series(False, index=out.index)
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
    out["rl_adj_deficit_without_cons2000_ha"] = (
        out["rl_adj_deficit_forest_without_cons2000_ha"] + out["rl_adj_deficit_cerrado_without_cons2000_ha"]
    )
    return out


def build_municipal_maps() -> tuple[Path, Path, Path, Path, Path, Path, Path, Path]:
    fc = pd.read_parquet(OUT_DIR / f"forest_code_mt_priority_consolidated_{TODAY}.parquet")
    status = fc["SITUACAO"].astype(str).str.upper()
    active = fc.loc[~status.str.contains("CANCELADO|INDEFERIDO|REJEIT", na=False)].copy()
    active["mun_code"] = active["mun_geocodigo"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    active = active[active["mun_code"].str.startswith("51")]
    active = add_lr_without_2000_rule(active)
    active["noncompliant"] = active["calc_deficit_total_ha"].fillna(0).gt(0)
    active["app_noncompliant"] = active["app_restore_ha"].fillna(0).gt(0)
    active["rl_noncompliant"] = active["rl_adj_deficit_ha"].fillna(0).gt(0)
    active["rl_without_2000_noncompliant"] = active["rl_adj_deficit_without_cons2000_ha"].fillna(0).gt(0)
    active["total_deficit_for_noncompliant"] = active["calc_deficit_total_ha"].where(active["noncompliant"], 0)
    active["app_deficit_for_noncompliant"] = active["app_restore_ha"].where(active["app_noncompliant"], 0)
    active["rl_deficit_for_noncompliant"] = active["rl_adj_deficit_ha"].where(active["rl_noncompliant"], 0)
    active["rl_without_2000_deficit_for_noncompliant"] = active["rl_adj_deficit_without_cons2000_ha"].where(
        active["rl_without_2000_noncompliant"], 0
    )

    summary = (
        active.groupby("mun_code", as_index=False)
        .agg(
            noncompliant_properties=("noncompliant", "sum"),
            app_noncompliant_properties=("app_noncompliant", "sum"),
            rl_noncompliant_properties=("rl_noncompliant", "sum"),
            rl_without_2000_noncompliant_properties=("rl_without_2000_noncompliant", "sum"),
            total_deficit_hectares=("total_deficit_for_noncompliant", "sum"),
            app_deficit_hectares=("app_deficit_for_noncompliant", "sum"),
            rl_deficit_hectares=("rl_deficit_for_noncompliant", "sum"),
            rl_without_2000_deficit_hectares=("rl_without_2000_deficit_for_noncompliant", "sum"),
            active_properties=("property_join_key", "size"),
        )
    )
    total_denominator = summary["noncompliant_properties"].mask(summary["noncompliant_properties"].eq(0))
    app_denominator = summary["app_noncompliant_properties"].mask(summary["app_noncompliant_properties"].eq(0))
    rl_denominator = summary["rl_noncompliant_properties"].mask(summary["rl_noncompliant_properties"].eq(0))
    rl_without_2000_denominator = summary["rl_without_2000_noncompliant_properties"].mask(
        summary["rl_without_2000_noncompliant_properties"].eq(0)
    )
    summary["deficit_per_noncompliant_property"] = (
        summary["total_deficit_hectares"].div(total_denominator).fillna(0).astype(float)
    )
    summary["app_deficit_per_noncompliant_property"] = (
        summary["app_deficit_hectares"].div(app_denominator).fillna(0).astype(float)
    )
    summary["rl_deficit_per_noncompliant_property"] = (
        summary["rl_deficit_hectares"].div(rl_denominator).fillna(0).astype(float)
    )
    summary["rl_without_2000_deficit_per_noncompliant_property"] = (
        summary["rl_without_2000_deficit_hectares"].div(rl_without_2000_denominator).fillna(0).astype(float)
    )

    geom_path = (
        ROOT
        / "data"
        / "raw"
        / "reference_maps"
        / "lml_municipio_a.parquet"
    )
    gdf = gpd.read_parquet(geom_path)
    gdf["mun_code"] = gdf["geocodigo"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    gdf = gdf[gdf["mun_code"].str.startswith("51")]
    mt = gdf.dissolve(by="mun_code", aggfunc={"nome": "first"}).reset_index()
    mt = mt.merge(summary, on="mun_code", how="left")
    for col in [
        "noncompliant_properties",
        "app_noncompliant_properties",
        "rl_noncompliant_properties",
        "rl_without_2000_noncompliant_properties",
        "total_deficit_hectares",
        "app_deficit_hectares",
        "rl_deficit_hectares",
        "rl_without_2000_deficit_hectares",
        "active_properties",
        "deficit_per_noncompliant_property",
        "app_deficit_per_noncompliant_property",
        "rl_deficit_per_noncompliant_property",
        "rl_without_2000_deficit_per_noncompliant_property",
    ]:
        mt[col] = mt[col].fillna(0)

    def stat_box(column: str, kind: str, properties_col: str | None = None, area_col: str | None = None) -> str:
        values = mt[column].astype(float)
        positive = values[values.gt(0)]
        header = []
        properties_total = None
        area_total = None
        if properties_col:
            properties_total = float(mt[properties_col].sum())
            header.append(f"Properties: {properties_total:,.0f}")
        if area_col:
            area_total = float(mt[area_col].sum())
            header.append(f"Area: {area_total:,.1f} hectares")
        if kind == "count":
            if not header:
                header = [f"Properties: {values.sum():,.0f}"]
            return "\n".join(header + [f"Mean: {values.mean():,.0f}", f"Median: {values.median():,.0f}", f"Max: {values.max():,.0f}"])
        if positive.empty:
            return "\n".join(header + ["No positive values"])
        weighted_mean = None
        if properties_total and area_total is not None and properties_total > 0:
            weighted_mean = area_total / properties_total
        mean_line = (
            f"Weighted mean: {weighted_mean:,.1f} hectares"
            if weighted_mean is not None
            else f"Mean: {positive.mean():,.1f} hectares"
        )
        return "\n".join(
            header
            + [
                mean_line,
                f"Municipal median: {positive.median():,.1f} hectares",
                f"Municipal P90: {positive.quantile(0.9):,.1f} hectares",
                f"Municipal max: {positive.max():,.1f} hectares",
            ]
        )

    def plot_classed_map(
        column: str,
        bins: list[float],
        labels: list[str],
        colors: list[str],
        path: Path,
        stats_text: str,
        legend_title: str,
    ) -> None:
        plt.rcParams.update({"font.family": "Arial", "font.size": 12})
        fig, ax = plt.subplots(figsize=(10, 7), dpi=170)
        ax.set_position([0.03, 0.08, 0.58, 0.84])
        cmap = ListedColormap(colors)
        norm = BoundaryNorm(bins, cmap.N)
        mt.plot(
            column=column,
            ax=ax,
            cmap=cmap,
            norm=norm,
            linewidth=0.25,
            edgecolor="#9aa6b2",
        )
        ax.set_axis_off()
        handles = [Patch(facecolor=color, edgecolor="#9aa6b2", label=label) for color, label in zip(colors, labels)]
        fig.legend(
            handles=handles,
            loc="lower left",
            bbox_to_anchor=(0.64, 0.08),
            ncol=1,
            frameon=True,
            fontsize=14,
            title_fontsize=14,
            title=legend_title,
            borderpad=0.6,
            columnspacing=1.1,
            labelspacing=0.3,
            handlelength=1.2,
        )
        ax.text(
            1.10,
            0.97,
            stats_text,
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=14,
            color=COLORS["ink"],
            bbox={
                "boxstyle": "round,pad=0.45",
                "facecolor": "white",
                "edgecolor": COLORS["line"],
                "alpha": 0.88,
            },
        )
        fig.savefig(path, facecolor="white", pad_inches=0.04)
        plt.close(fig)

    plot_classed_map(
        "noncompliant_properties",
        [-0.1, 0, 50, 250, 1_000, 2_000, float("inf")],
        ["0", "1-50", "51-250", "251-1,000", "1,001-2,000", ">2,000"],
        GRAY_SCALE,
        MAP_COUNT_PATH,
        stat_box("noncompliant_properties", "count", "noncompliant_properties", "total_deficit_hectares"),
        "Affected properties (count)",
    )
    plot_classed_map(
        "deficit_per_noncompliant_property",
        [-0.1, 0, 10, 50, 100, 250, float("inf")],
        ["No non-compliant", "0.1-10", "10.1-50", "50.1-100", "100.1-250", ">250"],
        ORANGE_SCALE,
        MAP_HECTARES_PATH,
        stat_box("deficit_per_noncompliant_property", "intensity", "noncompliant_properties", "total_deficit_hectares"),
        "Total Forest Code deficit\n(hectares per affected property)",
    )
    plot_classed_map(
        "app_noncompliant_properties",
        [-0.1, 0, 50, 250, 1_000, 2_000, float("inf")],
        ["0", "1-50", "51-250", "251-1,000", "1,001-2,000", ">2,000"],
        GRAY_SCALE,
        MAP_APP_PATH,
        stat_box("app_noncompliant_properties", "count", "app_noncompliant_properties", "app_deficit_hectares"),
        "APP-affected properties (count)",
    )
    plot_classed_map(
        "app_deficit_per_noncompliant_property",
        [-0.1, 0, 10, 50, 100, 250, float("inf")],
        ["No APP non-compliant", "0.1-10", "10.1-50", "50.1-100", "100.1-250", ">250"],
        ORANGE_SCALE,
        MAP_APP_HECTARES_PATH,
        stat_box("app_deficit_per_noncompliant_property", "intensity", "app_noncompliant_properties", "app_deficit_hectares"),
        "APP restoration deficit\n(hectares per APP-affected property)",
    )
    plot_classed_map(
        "rl_noncompliant_properties",
        [-0.1, 0, 10, 50, 100, 250, float("inf")],
        ["0", "1-10", "11-50", "51-100", "101-250", ">250"],
        GRAY_SCALE,
        MAP_RL_PATH,
        stat_box("rl_noncompliant_properties", "count", "rl_noncompliant_properties", "rl_deficit_hectares"),
        "LR-affected properties (count)",
    )
    plot_classed_map(
        "rl_without_2000_noncompliant_properties",
        [-0.1, 0, 10, 50, 100, 250, float("inf")],
        ["0", "1-10", "11-50", "51-100", "101-250", ">250"],
        GRAY_SCALE,
        MAP_RL_WITHOUT_2000_PATH,
        stat_box(
            "rl_without_2000_noncompliant_properties",
            "count",
            "rl_without_2000_noncompliant_properties",
            "rl_without_2000_deficit_hectares",
        ),
        "LR-affected properties without 2000 rule (count)",
    )
    plot_classed_map(
        "rl_deficit_per_noncompliant_property",
        [-0.1, 0, 10, 50, 100, 250, float("inf")],
        ["No LR non-compliant", "0.1-10", "10.1-50", "50.1-100", "100.1-250", ">250"],
        ORANGE_SCALE,
        MAP_RL_HECTARES_PATH,
        stat_box("rl_deficit_per_noncompliant_property", "intensity", "rl_noncompliant_properties", "rl_deficit_hectares"),
        "Adjusted LR deficit\n(hectares per LR-affected property)",
    )
    plot_classed_map(
        "rl_without_2000_deficit_per_noncompliant_property",
        [-0.1, 0, 10, 50, 100, 250, float("inf")],
        ["No LR non-compliant", "0.1-10", "10.1-50", "50.1-100", "100.1-250", ">250"],
        ORANGE_SCALE,
        MAP_RL_WITHOUT_2000_HECTARES_PATH,
        stat_box(
            "rl_without_2000_deficit_per_noncompliant_property",
            "intensity",
            "rl_without_2000_noncompliant_properties",
            "rl_without_2000_deficit_hectares",
        ),
        "LR deficit without 2000 rule\n(hectares per LR-affected property)",
    )
    return (
        MAP_COUNT_PATH,
        MAP_HECTARES_PATH,
        MAP_APP_PATH,
        MAP_APP_HECTARES_PATH,
        MAP_RL_PATH,
        MAP_RL_HECTARES_PATH,
        MAP_RL_WITHOUT_2000_PATH,
        MAP_RL_WITHOUT_2000_HECTARES_PATH,
    )


def build_paper_map_panel(map_paths: tuple[Path, Path, Path, Path, Path, Path, Path, Path]) -> tuple[Path, Path]:
    """Render two readable 2 x 2 panels instead of one illegible eight-map sheet."""
    labels = [
        "All non-compliance — properties", "All — hectares per affected property",
        "APP non-compliance — properties", "APP — hectares per affected property",
        "LR with 2000 rule — properties", "LR with 2000 rule — hectares per affected property",
        "LR without 2000 rule — properties", "LR without 2000 rule — hectares per affected property",
    ]
    outputs = []
    for page, destination in enumerate((PAPER_MAP_PANEL_PATH, PAPER_MAP_PANEL_2_PATH)):
        panel = Image.new("RGB", (3000, 1700), COLORS["white"])
        draw = ImageDraw.Draw(panel)
        for local_idx, (x, y) in enumerate(((90, 100), (1530, 100), (90, 900), (1530, 900))):
            idx = page * 4 + local_idx
            draw.text((x, y - 60), labels[idx], font=font(50, True), fill=COLORS["ink"])
            with Image.open(map_paths[idx]) as src:
                tile = src.convert("RGB").resize((1360, 760), Image.Resampling.LANCZOS)
            panel.paste(tile, (x, y))
        panel.save(destination, quality=95)
        outputs.append(destination)
    return tuple(outputs)


PT = {
    "title": "Conformidade com o Codigo Florestal em Mato Grosso",
    "subtitle": "Resultados por propriedade em Mato Grosso, reportados em hectares",
    "final": "FINAL",
    "qa": "QA OK",
    "prepared": "Preparado",
    "specimen": "Amostra",
    "specimen_text": "Universo CAR priorizado como SIMCAR validado > SIMCAR digital > SIMCAR proxy",
    "method": "Metodo",
    "method_text": "Contabilidade estilo MS Masson: passivo ajustado de RL + passivo restauravel de APP",
    "car_section": "Entradas CAR e QA dos Dados",
    "prioritized": "Universo CAR priorizado",
    "active": "Universo analitico ativo",
    "inactive": "Inativos excluidos",
    "precision": "Hierarquia de precisao CAR",
    "validated": "SIMCAR validado",
    "digital": "SIMCAR digital",
    "proxy": "SIMCAR proxy",
    "native": "Base de vegetacao nativa",
    "zero": "Codigos municipais zero",
    "legal_tables": "tabelas legais",
    "records": "registros",
    "properties": "propriedades",
    "must_zero": "deve ser zero",
    "forest_cerrado": "Floresta + Cerrado",
    "liability_section": "Passivo de Reserva Legal e APP",
    "final_liability": "Passivo final combinado",
    "gross": "Deficit bruto combinado",
    "compliant": "Propriedades conformes",
    "lr_adj": "Passivo ajustado de RL",
    "app_rest": "Passivo de restauracao APP",
    "restore": "Passivo de restauracao",
    "comp": "Passivo de compensacao",
    "surplus": "Excedente de RL",
    "large": "Concentracao em grandes propriedades",
    "before": "antes do ajuste",
    "main": "principal vetor",
    "restorable": "APP restauravel",
    "lr_app": "RL + APP",
    "lr_only": "somente RL",
    "offset": "compensacao potencial",
    "scenarios": "Cenarios e Sinais Territoriais",
    "without_2000": "Sem regra de RL de 2000",
    "effect_2000": "Efeito da regra de 2000",
    "secondary_mapped": "Floresta secundaria mapeada",
    "secondary_liab": "Passivo com floresta secundaria",
    "secondary_reduction": "Reducao por floresta secundaria",
    "top20": "20 municipios principais",
    "sensitivity": "sensibilidade",
    "increment": "incremento",
    "vegetation": "vegetacao",
    "scenario_total": "total do cenario",
    "newly": "novas conformes",
    "of_total": "do total",
    "active_note": "ativas",
    "liability_note": "do passivo",
    "supply": "Exposicao da Cadeia de Fornecimento",
    "all_suppliers": "Todos fornecedores ligados a GTA",
    "direct_bin": "Fornecedores diretos (>0 abate/export.)",
    "direct_only": "  Somente direto",
    "direct_t1": "  Direto + Tier 1",
    "direct_gt50": "  Intensidade direta (>50% saida)",
    "indirect": "Fornecedores indiretos (sem direto)",
    "tier_note": "Tier 1 e Tier 2+",
    "tier1": "  Somente Tier 1",
    "tier2": "  Tier 2+",
    "binary": "regra binaria; sobrepoe indireto",
    "head": "cabecas",
    "municipal": "Mapas Municipais de Nao Conformidade",
    "map_all_n": "Todas nao conformidades: propriedades",
    "map_all_ha": "Todas: hectares/propriedade afetada",
    "map_app_n": "APP nao conforme: propriedades",
    "map_app_ha": "APP: hectares/propriedade APP afetada",
    "map_lr_2000_n": "RL com regra de 2000: propriedades",
    "map_lr_2000_ha": "RL com regra de 2000: hectares/propriedade",
    "map_lr_no2000_n": "RL sem regra de 2000: propriedades",
    "map_lr_no2000_ha": "RL sem regra de 2000: hectares/propriedade",
}


def build_png(language: str = "en"):
    pt = language == "pt"
    text = PT if pt else {}
    out_path = PNG_PT_PATH if pt else PNG_PATH

    def tt(key: str, default: str) -> str:
        return text.get(key, default)

    def props_unit() -> str:
        return tt("properties", "properties")

    def row_pa_local(draw, x, y, w, label, properties, hectares, tone="info", note="", bg=None):
        prop_text = f"{fmt_num(properties)}"
        area_text = f"{fmt_num(hectares, 1)} hectares"
        ref = area_text if not note else f"{area_text}\n{note}"
        return row(draw, x, y, w, label, prop_text, props_unit(), ref, tone, bg=bg)

    def row_record_area_local(draw, x, y, w, label, records, hectares, tone="info", unit="records", bg=None):
        return row(draw, x, y, w, label, fmt_num(records), unit, f"{fmt_num(hectares, 1)} hectares", tone, bg=bg)

    d = read_results()
    (
        map_count_path,
        map_hectares_path,
        map_app_path,
        map_app_hectares_path,
        map_rl_path,
        map_rl_hectares_path,
        map_rl_without_2000_path,
        map_rl_without_2000_hectares_path,
    ) = build_municipal_maps()
    map_paths = (
        map_count_path,
        map_hectares_path,
        map_app_path,
        map_app_hectares_path,
        map_rl_path,
        map_rl_hectares_path,
        map_rl_without_2000_path,
        map_rl_without_2000_hectares_path,
    )
    build_paper_map_panel(map_paths)
    W, H = 3300, 3440
    img = Image.new("RGB", (W, H), COLORS["white"])
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, W, 230), fill=COLORS["blue"])
    draw.text((70, 42), tt("title", "Forest Code Compliance in Mato Grosso"), font=F["title"], fill=COLORS["white"])
    draw.text((72, 118), tt("subtitle", "Mato Grosso property-level Forest Code results, reported in hectares"), font=F["subtitle"], fill="#dbeafe")
    flag(draw, W - 560, 52, tt("final", "FINAL"), "ok")
    flag(draw, W - 420, 52, tt("qa", "QA PASS"), "ok")
    draw.text((W - 560, 116), f"{tt('prepared', 'Prepared')} {TODAY[:4]}-{TODAY[4:6]}-{TODAY[6:]}", font=F["small"], fill="#dbeafe")

    draw.text((72, 262), tt("specimen", "Specimen"), font=F["label"], fill=COLORS["muted"])
    draw.text((210, 262), tt("specimen_text", "CAR property universe prioritized as SIMCAR validated > SIMCAR digital > SIMCAR proxy"), font=F["body"], fill=COLORS["ink"])
    draw.text((72, 302), tt("method", "Method"), font=F["label"], fill=COLORS["muted"])
    draw.text((210, 302), tt("method_text", "MS Masson-style Forest Code accounting: adjusted LR liability + restorable APP liability"), font=F["body"], fill=COLORS["ink"])

    margin, gap = 60, 30
    col_w = (W - 2 * margin - 2 * gap) // 3
    footer_y = 1580
    top, bottom = 365, footer_y - 26
    boxes = [
        (margin, top, margin + col_w, bottom),
        (margin + col_w + gap, top, margin + 2 * col_w + gap, bottom),
        (margin + 2 * (col_w + gap), top, W - margin, bottom),
    ]

    x, y, w = section(draw, boxes[0], tt("car_section", "CAR Inputs and Data QA"))
    y = row_record_area_local(draw, x, y, w, tt("prioritized", "Prioritized CAR universe"), d["records"], d["total_area_mha"] * 1_000_000, "info", props_unit())
    y = row_pa_local(draw, x, y, w, tt("active", "Active analytical universe"), d["active_properties"], d["active_area_mha"] * 1_000_000, "ok", tt("legal_tables", "legal tables"))
    y = row_record_area_local(draw, x, y, w, tt("inactive", "Inactive excluded"), d["inactive"], (d["total_area_mha"] - d["active_area_mha"]) * 1_000_000, "info", props_unit())
    y += 10
    draw.text((x, y), tt("precision", "CAR precision hierarchy"), font=F["label"], fill=COLORS["ink"])
    y += 36
    y = row_pa_local(draw, x, y, w, tt("validated", "SIMCAR validated"), d["validated"], d["validated_area"], "ok", f"{d['validated'] / d['records'] * 100:.1f}% {tt('records', 'records')}")
    y = row_pa_local(draw, x, y, w, tt("digital", "SIMCAR digital"), d["digital"], d["digital_area"], "info", f"{d['digital'] / d['records'] * 100:.1f}% {tt('records', 'records')}")
    y = row_pa_local(draw, x, y, w, tt("proxy", "SIMCAR proxy"), d["proxy"], d["proxy_area"], "watch", f"{d['proxy'] / d['records'] * 100:.1f}% {tt('records', 'records')}")
    y += 10
    y = row_pa_local(draw, x, y, w, tt("native", "Native vegetation basis"), d["active_properties"], d["native_basis"], "info", tt("forest_cerrado", "Forest + Cerrado"))
    y = row_pa_local(draw, x, y, w, tt("zero", "Municipality zero-code findings"), d["zero_codes"], 0.0, "ok", tt("must_zero", "must be zero"))

    x, y, w = section(draw, boxes[1], tt("liability_section", "Legal Reserve and APP Liability"))
    y = row_pa_local(draw, x, y, w, tt("final_liability", "Final combined liability"), d["liability_n"], d["final_liability"], "high", tt("lr_app", "LR + APP"))
    y = row_pa_local(draw, x, y, w, tt("gross", "Gross combined deficit"), d["gross_liability_n"], d["gross_combined"], "high", tt("before", "before adjustment"))
    y = row_pa_local(draw, x, y, w, tt("compliant", "Compliant properties"), d["compliant"], 0.0, "ok", f"{d['compliant_pct']:.1f}% {tt('active_note', 'active')}")
    y = row_pa_local(draw, x, y, w, tt("lr_adj", "LR adjusted liability"), d["lr_liability_n"], d["lr_adjusted"], "high", tt("main", "main driver"))
    y = row_pa_local(draw, x, y, w, tt("app_rest", "APP restoration liability"), d["app_liability_n"], d["app_restore"], "watch", tt("restorable", "restorable APP"))
    y = row_pa_local(draw, x, y, w, tt("restore", "Restoration liability"), d["restore_n"], d["restore"], "watch", tt("lr_app", "LR + APP"))
    y = row_pa_local(draw, x, y, w, tt("comp", "Compensation liability"), d["compensate_n"], d["compensate"], "high", tt("lr_only", "LR only"))
    y = row_pa_local(draw, x, y, w, tt("surplus", "LR surplus"), d["surplus_n"], d["lr_surplus"], "info", tt("offset", "potential offset"))
    y = row_pa_local(draw, x, y, w, tt("large", "Large-property concentration"), d["large_active_n"], d["large_liability"], "high", f"{d['large_share']:.1f}% {tt('liability_note', 'liability')}")

    x, y, w = section(draw, boxes[2], tt("scenarios", "Scenarios and Territorial Signals"))
    y = row_pa_local(draw, x, y, w, tt("without_2000", "Without 2000 LR rule"), d["without_2000_n"], d["without_2000"], "high", tt("sensitivity", "sensitivity"))
    y = row_pa_local(draw, x, y, w, tt("effect_2000", "2000-rule effect"), d["without_2000_delta_n"], d["without_2000_delta"], "high", tt("increment", "increment"))
    y = row_pa_local(draw, x, y, w, tt("secondary_mapped", "Secondary forest mapped"), d["secondary_properties"], d["secondary_area"], "info", tt("vegetation", "vegetation"))
    y = row_pa_local(draw, x, y, w, tt("secondary_liab", "Liability with secondary forest"), d["secondary_liability_n"], d["secondary_liability"], "watch", tt("scenario_total", "scenario total"))
    y = row_pa_local(draw, x, y, w, tt("secondary_reduction", "Secondary-forest reduction"), d["newly_compliant"], d["secondary_reduction"], "ok", tt("newly", "newly compliant"))
    y = row_pa_local(draw, x, y, w, tt("top20", "Top 20 municipalities"), d["top20_properties"], d["top20_total"], "high", f"{d['top20_share']:.1f}% {tt('of_total', 'of total')}")
    y += 10
    draw.rectangle((x, y, x + w, y + 42), fill=COLORS["blue_light"])
    draw.text((x + 12, y + 8), tt("supply", "Supply Chain Exposure"), font=F["label"], fill=COLORS["blue"])
    y += 50
    y = row_pa_local(draw, x, y, w, tt("all_suppliers", "All GTA-linked suppliers"), d["gta_properties"], d["gta_liability"], "high", f"{fmt_num(d['cattle_head'])} {tt('head', 'cattle head')}")
    y = row_pa_local(
        draw,
        x,
        y,
        w,
        tt("direct_bin", "Direct suppliers (>0 abate/export)"),
        d["binary_direct_n"],
        d["binary_direct_liability"],
        "high",
        tt("binary", "binary rule; overrides indirect"),
        bg=COLORS["direct_light"],
    )
    for label, key, tone, bg in [
        (tt("direct_only", "  Direct only"), "Direct pure", "high", COLORS["direct_light"]),
        (tt("direct_t1", "  Direct + Tier 1"), "Direct also Tier 1", "high", COLORS["direct_mixed_light"]),
    ]:
        vals = d["supplier_subgroups"].get(key, {"properties": 0, "liability": 0.0, "cattle": 0})
        y = row_pa_local(
            draw,
            x,
            y,
            w,
            label,
            int(vals["properties"]),
            float(vals["liability"]),
            tone,
            f"{fmt_num(float(vals['cattle']))} {tt('head', 'cattle head')}",
            bg=bg,
        )
    y = row_pa_local(
        draw,
        x,
        y,
        w,
                tt("direct_gt50", "  Direct intensity (>50% outflow)"),
        d["direct_gt50_n"],
        d["direct_gt50_liability"],
        "high",
                f"{fmt_num(d['direct_gt50_cattle'])} {tt('head', 'head')}",
        bg=COLORS["gt50_light"],
    )
    y = row_pa_local(
        draw,
        x,
        y,
        w,
        tt("indirect", "Indirect suppliers (no direct)"),
        d["indirect_properties"],
        d["tier1_liability"] + d["tier2_liability"],
        "watch",
        tt("tier_note", "Tier 1 and Tier 2+"),
        bg=COLORS["tier1_light"],
    )
    for label, key, tone, bg in [
        (tt("tier1", "  Tier 1 only"), "Tier 1 pure", "watch", COLORS["tier1_light"]),
        (tt("tier2", "  Tier 2+"), "Tier 2+", "watch", COLORS["tier2_light"]),
    ]:
        vals = d["supplier_subgroups"].get(key, {"properties": 0, "liability": 0.0, "cattle": 0})
        y = row_pa_local(
            draw,
            x,
            y,
            w,
            label,
            int(vals["properties"]),
            float(vals["liability"]),
            tone,
            f"{fmt_num(float(vals['cattle']))} {tt('head', 'cattle head')}",
            bg=bg,
        )

    # Footer strip with municipal maps and compact territorial notes.
    draw.rectangle((60, footer_y, W - 60, H - 58), fill=COLORS["gray_light"], outline=COLORS["line"], width=2)
    draw.text((88, footer_y + 22), tt("municipal", "Municipal Non-compliance Maps"), font=F["label"], fill=COLORS["ink"])
    map_specs = [
        (map_count_path, 88, footer_y + 92, tt("map_all_n", "All non-compliance: properties")),
        (map_hectares_path, 890, footer_y + 92, tt("map_all_ha", "All: hectares/affected property")),
        (map_app_path, 1692, footer_y + 92, tt("map_app_n", "APP non-compliance: properties")),
        (map_app_hectares_path, 2494, footer_y + 92, tt("map_app_ha", "APP: hectares/APP-affected property")),
        (map_rl_path, 88, footer_y + 910, tt("map_lr_2000_n", "LR with 2000 rule: properties")),
        (map_rl_hectares_path, 890, footer_y + 910, tt("map_lr_2000_ha", "LR with 2000 rule: hectares/property")),
        (map_rl_without_2000_path, 1692, footer_y + 910, tt("map_lr_no2000_n", "LR without 2000 rule: properties")),
        (map_rl_without_2000_hectares_path, 2494, footer_y + 910, tt("map_lr_no2000_ha", "LR without 2000 rule: hectares/property")),
    ]
    for path, mx, my, caption in map_specs:
        with Image.open(path) as src:
            map_img = src.convert("RGB").resize((730, 730), Image.Resampling.LANCZOS)
        draw_text(draw, (mx, my - 46), caption, F["tiny"], fill=COLORS["muted"], max_width=710, line_gap=1)
        img.paste(map_img, (mx, my))

    img.save(out_path, quality=95)
    print(out_path)


if __name__ == "__main__":
    build_png()
    build_png("pt")

