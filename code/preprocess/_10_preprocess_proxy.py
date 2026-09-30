from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from _11_forest_code_compliance import compute_forest_code_metrics as forest_code_compliance
import _00_paths as _paths

PACKAGE_ROOT = Path(os.environ.get("FCM_ROOT", Path(__file__).resolve().parents[3]))
RAW_DIR = Path(os.environ.get("FCM_RAW_DIR", PACKAGE_ROOT / "data" / "raw"))
PREPROCESSED_DIR = Path(os.environ.get("FCM_PREPROCESSED_DIR", PACKAGE_ROOT / "data" / "pre"))

# Forest Code parameters.
CONFIG: dict[str, Any] = {
    "paths": {
        "intersect_dir": RAW_DIR / "simcar_proxy",
        "car_atp": RAW_DIR / "simcar_requerido" / "CAR_ATP.parquet",
        "output_dir": PREPROCESSED_DIR / "car_proxy",
    },
    "join_key": "car_join",
    "status_rank": {
        "[CANCELADO]": 0,
        "[INDEFERIDO]": 0,
        "[SUSPENSO]": 0,
        "[CAR_VALIDADO]": 9,
        "[CAR_VALIDADO_EM_REGULARIZACAO]": 8,
        "[AGUARDANDO_ANALISE_PRA]": 7,
        "[AGUARDANDO_ENVIO_PRA]": 6,
        "[EM_ANALISE]": 5,
        "[AGUARDANDO_ANALISE]": 4,
        "[AGUARDANDO_COMPLEMENTACAO]": 3,
    },
    "invalid_pat": ["CANCEL", "INDEFER", "SUSPEN", "NAO_ACEIT", "REJEIT"],
    "radam_label": "SIMCAR_P_vegetacao_radambrasil",
    "nveg_radam_label": "SIMCAR_P_native_veg_x_radam",
    "fitoecolog_col": "FITOECOLOG",
    "forest_label": "FLORESTA",
    "cerrado_label": "CERRADO",
}

SIZE_LEVELS = [
    "Minifundio (<1 MF)",
    "Small (1-4 MF)",
    "Medium (>4-15 MF)",
    "Large (>15 MF)",
    "Not Classified",
]

MIN_MAPPING_UNIT_CONSOLIDATED_2000_HA = 6.25


def out_dir() -> Path:
    path = Path(CONFIG["paths"]["output_dir"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.to_list()
    if pd.isna(value):
        return None
    return str(value)


def save_json(obj: Any, filename: str) -> Path:
    path = out_dir() / filename
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")
    return path


def is_invalid(x: Any) -> bool:
    val = str(x).upper()
    return any(pat in val for pat in CONFIG["invalid_pat"])


def get_rank(x: Any) -> int:
    return int(CONFIG["status_rank"].get(str(x), 1))


def make_size_class(mf: Any) -> str:
    if pd.isna(mf) or float(mf) == 0:
        return "Not Classified"
    mf = float(mf)
    if mf < 1:
        return "Minifundio (<1 MF)"
    if mf <= 4:
        return "Small (1-4 MF)"
    if mf <= 15:
        return "Medium (>4-15 MF)"
    return "Large (>15 MF)"


def read_pq(path: str | Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    for col in ("geometry", "geometry_bbox"):
        if col in df.columns:
            df = df.drop(columns=col)
    return df


def best_key(df: pd.DataFrame) -> str:
    if CONFIG["join_key"] in df.columns:
        return CONFIG["join_key"]
    if "prop_id_unique" in df.columns:
        return "prop_id_unique"
    raise KeyError(f"No join key found in columns: {list(df.columns)}")


def clean_municipality_code(value: Any) -> str | None:
    if pd.isna(value):
        return None
    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "none", "<na>"}:
        return None
    raw = raw.removesuffix(".0")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits or set(digits) == {"0"}:
        return None
    if len(digits) >= 7:
        return digits[:7]
    return digits.zfill(7)


def derive_municipality_code(df: pd.DataFrame) -> pd.Series:
    # MUNICIPIO_ is a dedicated geocode attribute and must outrank car_code /
    # NUMEROESTA: those are composite identifiers (protocol number, year, and
    # CAR hash concatenated) that only "look like" a geocode by digit-length
    # coincidence. When CODIGO_CAR/CAR_FEDERA are both absent (e.g. a
    # registration still awaiting analysis, with car_code truncated to just
    # "MT<protocol>/<year>-"), extracting digits from car_code silently
    # concatenates the protocol number with the year into a bogus 7-digit
    # code that resolves to a real (but wrong) municipality elsewhere in
    # Brazil, rather than surfacing as missing.
    out = pd.Series(pd.NA, index=df.index, dtype="string")
    for col in ["CODIGO_CAR", "CAR_FEDERA", "MUNICIPIO_", "car_code", "NUMEROESTA"]:
        if col not in df.columns:
            continue
        codes = df[col].map(clean_municipality_code).astype("string")
        out = out.where(out.notna(), codes)
    return out.mask(out.str.fullmatch(r"0+").fillna(False))


def col_or_zero(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0)
    return pd.Series(0.0, index=df.index)


def sum_cols(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    if not cols:
        return pd.Series(0.0, index=df.index)
    return df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)


def make_parquet_safe(df: pd.DataFrame) -> pd.DataFrame:
    # CAR-derived tables frequently include nominal fields exported as object
    # dtype with mixed Python values, such as mostly strings plus a small
    # number of integers or float placeholders. Arrow-backed Parquet writing
    # requires a single coherent physical type per column, so mixed object
    # columns can fail at export time even when the analytical workflow itself
    # runs correctly. This helper creates an export-safe copy by coercing only
    # mixed object columns to pandas' nullable string dtype, preserving nulls
    # while avoiding changes to the in-memory analytical table.
    safe = df.copy()
    for col in safe.select_dtypes(include=["object"]).columns:
        non_null = safe[col].dropna()
        if non_null.empty:
            safe[col] = safe[col].astype("string")
            continue
        py_types = non_null.map(lambda x: type(x).__name__).unique().tolist()
        if len(py_types) > 1:
            safe[col] = safe[col].astype("string")
    return safe


def read_sum(path: str | Path, out_col: str) -> pd.DataFrame:
    df = read_pq(path)
    key = best_key(df)
    path_name = Path(path).stem.lower()
    if "cons_area_2000" in path_name:
        before_rows = len(df)
        before_area = pd.to_numeric(df["area_ha"], errors="coerce").fillna(0).sum()
        df = df[pd.to_numeric(df["area_ha"], errors="coerce").fillna(0) >= MIN_MAPPING_UNIT_CONSOLIDATED_2000_HA].copy()
        after_area = pd.to_numeric(df["area_ha"], errors="coerce").fillna(0).sum()
        print(
            f"    Applied PRODES 2000 MMU >= {MIN_MAPPING_UNIT_CONSOLIDATED_2000_HA} ha to {Path(path).name}: "
            f"{before_rows:,} -> {len(df):,} rows; removed {before_area - after_area:,.2f} ha"
        )
    return (
        df.groupby(key, as_index=False)["area_ha"]
        .sum()
        .rename(columns={key: CONFIG["join_key"], "area_ha": out_col})
    )


def read_fito(path: str | Path, prefix: str) -> pd.DataFrame | None:
    df = read_pq(path)
    key = best_key(df)
    fito = CONFIG["fitoecolog_col"]
    if fito not in df.columns:
        print(f"  [WARN] FITOECOLOG not found in {Path(path).name}")
        return None
    work = df[[key, fito, "area_ha"]].copy()
    work[fito] = work[fito].astype(str).str.strip().str.upper()
    agg = work.groupby([key, fito], as_index=False)["area_ha"].sum()
    wide = agg.pivot_table(index=key, columns=fito, values="area_ha", fill_value=0, aggfunc="sum").reset_index()
    wide.columns = [col if col == key else f"{prefix}_{col}_ha" for col in wide.columns]
    return wide.rename(columns={key: CONFIG["join_key"]})


def discover_layers() -> pd.DataFrame:
    print("STEP 1: Discovering intersect parquets...")
    # This step inventories the already-produced intersect outputs. The model
    # assumes that upstream spatial processing has already localized APP, RL-
    # relevant land cover, and other environmental attributes for each CAR
    # property. In legal terms, these layers operationalize information that
    # would otherwise be reported in CAR under Art. 29, Section 1, Item III.
    rows = []
    for path in sorted(Path(CONFIG["paths"]["intersect_dir"]).glob("*.parquet")):
        stem = path.stem
        label = stem.removesuffix("_x_car_atp")
        short = label.removeprefix("SIMCAR_P_")
        rows.append({
            "path": str(path),
            "label": label,
            "short": short,
            "is_radam": label == CONFIG["radam_label"],
            "is_nveg_radam": label == CONFIG["nveg_radam_label"],
            "type": "RADAM" if label == CONFIG["radam_label"] else "nveg_radam" if label == CONFIG["nveg_radam_label"] else "regular",
        })
    if not rows:
        raise FileNotFoundError("No parquet files found in intersect_dir.")
    save_json(rows, "layers_meta.json")
    return pd.DataFrame(rows)


def load_car() -> tuple[pd.DataFrame, pd.DataFrame]:
    print("\nSTEP 2: Loading CAR_ATP...")
    jk = CONFIG["join_key"]
    car = read_pq(CONFIG["paths"]["car_atp"]).copy()
    if jk not in car.columns:
        raise KeyError(f"'{jk}' not in CAR_ATP.")
    if "area_ha_car" not in car.columns:
        print("[WARN] area_ha_car not found; falling back to AREA_HA")
        car["area_ha_car"] = pd.to_numeric(car.get("AREA_HA", 0), errors="coerce").fillna(0)
    car["SITUACAO"] = car.get("SITUACAO", "").astype(str)
    car["CODIGO_CAR"] = car.get("CODIGO_CAR", "").astype(str)
    car["mun_geocodigo"] = derive_municipality_code(car)

    # The validity flag is an administrative screening device rather than a
    # direct legal category from Law No. 12,651/2012. It is used here to
    # separate active and inactive registrations so that descriptive outputs
    # match operational registry practice while preserving the underlying CAR
    # record required under Art. 29.
    car["car_valid"] = ~car["SITUACAO"].map(is_invalid)
    car["status_rank"] = car["SITUACAO"].map(get_rank)
    car["area_ha_car"] = pd.to_numeric(car["area_ha_car"], errors="coerce").fillna(0)

    # Deduplicating on the property key ensures one analytical row per CAR.
    # The prioritization rule favors records that are both administratively
    # valid and spatially larger, which is a pragmatic way to resolve duplicate
    # exports without silently summing multiple administrative states.
    car = car.sort_values([jk, "car_valid", "area_ha_car", "status_rank"], ascending=[True, False, False, False])
    car = car.drop_duplicates(subset=[jk], keep="first").reset_index(drop=True)

    summary = (
        car.groupby(["car_valid", "SITUACAO", "status_rank"], as_index=False)
        .agg(n=(jk, "size"), area_ha_car=("area_ha_car", "sum"))
        .sort_values("status_rank")
        .reset_index(drop=True)
    )
    total_n = int(summary["n"].sum())
    total_area = float(summary["area_ha_car"].sum())
    summary["pct_n"] = (100 * summary["n"] / max(total_n, 1)).round(2)
    summary["pct_area"] = (100 * summary["area_ha_car"] / max(total_area, 1)).round(2)
    save_json(pd.concat([summary, pd.DataFrame([{"car_valid": None, "SITUACAO": "Total", "status_rank": None, "n": total_n, "area_ha_car": total_area, "pct_n": 100.0, "pct_area": 100.0}])], ignore_index=True), "car_summary.json")
    return car, summary


def save_summary_plot(car: pd.DataFrame) -> Path:
    plot_df = (
        car.groupby(["car_valid", "SITUACAO", "status_rank"], as_index=False)
        .agg(n=(CONFIG["join_key"], "size"), area_ha_car=("area_ha_car", "sum"))
    )
    if plot_df.empty:
        return out_dir() / "SM_1_summaryProp.png"
    plot_df["car_valid_label"] = np.where(plot_df["car_valid"], "VALID CAR", "INVALID CAR")
    statuses = plot_df.groupby("SITUACAO", as_index=False)["n"].sum().sort_values("n")["SITUACAO"].tolist()
    fig, axes = plt.subplots(2, 1, figsize=(13.33, 7.5))
    colors = {"VALID CAR": "#4C956C", "INVALID CAR": "#D1495B"}
    for ax, metric, title in zip(axes, ["n", "area_ha_car"], ["TOTAL NUMBER OF PROPERTIES", "TOTAL AREA IN HECTARES"]):
        piv = plot_df.pivot_table(index="SITUACAO", columns="car_valid_label", values=metric, aggfunc="sum", fill_value=0).reindex(statuses).fillna(0)
        left = np.zeros(len(piv))
        for label in ["VALID CAR", "INVALID CAR"]:
            vals = piv[label].to_numpy() if label in piv.columns else np.zeros(len(piv))
            ax.barh(piv.index, vals, left=left, color=colors[label], label=label)
            left += vals
        ax.set_title(title)
        ax.grid(axis="x", alpha=0.2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    fig.suptitle("DISTRIBUTION OF CAR STATUS BY VALIDITY CLASS")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    path = out_dir() / "SM_1_summaryProp.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


def read_layers(layers_meta: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    print("\nSTEP 3: Reading intersect layers...")
    layer_list: dict[str, pd.DataFrame] = {}
    read_log: list[dict[str, Any]] = []
    for idx, row in layers_meta.reset_index(drop=True).iterrows():
        print(f"  [{idx + 1}/{len(layers_meta)}] {row['label']}")
        try:
            if row["is_radam"]:
                # RADAM is used here as a biome-fitophysiognomy proxy to
                # operationalize Art. 12, Section I, letters a and b, as well
                # as Art. 12, Section 2, which requires separate treatment of
                # forest and cerrado fractions in the Legal Amazon.
                data = read_fito(row["path"], prefix="radam")
                if data is not None:
                    layer_list["radam"] = data
                read_log.append({"label": row["label"], "status": "OK", "key": "radam", "rows": 0 if data is None else len(data)})
            elif row["is_nveg_radam"]:
                # Native vegetation crossed with RADAM provides the biome-
                # specific vegetation stock needed to compare existing native
                # vegetation against RL requirements, especially under Arts. 15,
                # 17, and 18.
                data = read_fito(row["path"], prefix="nveg")
                if data is not None:
                    layer_list["nveg_radam"] = data
                read_log.append({"label": row["label"], "status": "OK", "key": "nveg_radam", "rows": 0 if data is None else len(data)})
            else:
                data = read_sum(row["path"], out_col=row["short"])
                layer_list[row["short"]] = data
                read_log.append({"label": row["label"], "status": "OK", "key": row["short"], "rows": len(data)})
        except Exception as exc:
            read_log.append({"label": row["label"], "status": "ERROR", "key": row["short"], "message": str(exc)})
    read_log_df = pd.DataFrame(read_log)
    save_json(read_log_df, "read_log.json")
    return layer_list, read_log_df

def dissolve_layers(layer_list: dict[str, pd.DataFrame], car: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    print("\nSTEP 4: Dissolving layers by car_join...")
    rows = []
    out: dict[str, pd.DataFrame] = {}
    n_car_unique = car[CONFIG["join_key"]].nunique()
    for name, frame in layer_list.items():
        diss = frame.groupby(CONFIG["join_key"], as_index=False).sum(numeric_only=True)
        out[name] = diss
        n_rows = len(diss)
        n_unique = diss[CONFIG["join_key"]].nunique()
        dups = n_rows - n_unique
        rows.append({
            "layer": name,
            "n_car_unique": n_car_unique,
            "n_rows": n_rows,
            "n_unique_key": n_unique,
            "n_duplicates": dups,
            "pct_coverage": round(n_unique / max(n_car_unique, 1) * 100, 1),
            "status": "OK" if dups == 0 else f"WARN: {dups} dups",
        })
    check = pd.DataFrame(rows)
    save_json(check, "dissolve_check.json")
    return out, check


def build_match_table(layer_list: dict[str, pd.DataFrame], car: pd.DataFrame) -> pd.DataFrame:
    print("\nSTEP 5: Match table...")
    car_keys = set(car[CONFIG["join_key"]].dropna())
    rows = []
    for name, frame in layer_list.items():
        keys = set(frame[CONFIG["join_key"]].dropna())
        matched = len(car_keys & keys)
        rows.append({
            "layer": name,
            "n_unique": len(keys),
            "matched": matched,
            "unmatched": len(car_keys) - matched,
            "foreign_keys": len(keys - car_keys),
            "pct_match": round(matched / max(len(car_keys), 1) * 100, 1),
        })
    match_tbl = pd.DataFrame(rows)
    save_json(match_tbl, "match_table.json")
    return match_tbl


def validate_exhaustive_intersections(match_tbl: pd.DataFrame) -> None:
    """Fail closed for layers whose spatial domain must cover every CAR.

    Sparse thematic layers (APP, rivers, settlements, declared areas, etc.) are
    expected to have unmatched properties: absence is a legitimate zero. RADAM
    is different because it partitions the full state into Forest/Cerrado and
    therefore must match essentially the entire CAR universe.
    """
    exhaustive = {"radam": 99.9}
    failures: list[str] = []
    for layer, minimum in exhaustive.items():
        row = match_tbl.loc[match_tbl["layer"].eq(layer)]
        if row.empty:
            failures.append(f"{layer}: missing intersection")
            continue
        coverage = float(row.iloc[0]["pct_match"])
        foreign = int(row.iloc[0].get("foreign_keys", 0))
        if coverage < minimum or foreign:
            failures.append(f"{layer}: coverage={coverage:.1f}% foreign_keys={foreign}")
    if failures:
        raise RuntimeError("Exhaustive spatial-intersection audit failed: " + "; ".join(failures))


def join_layers(car: pd.DataFrame, layer_list: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("\nSTEP 6: Joining all layers to CAR_ATP...")
    df = car.copy()
    original_cols = list(df.columns)
    jk = CONFIG["join_key"]

    # The analytical table is constructed as a left join on the CAR registry
    # base. This design preserves the CAR universe as the denominator for all
    # later compliance summaries, consistent with the registry-centered logic
    # of Art. 29 and the regularization architecture of Art. 59.
    for _, layer in layer_list.items():
        df = df.merge(layer, on=jk, how="left")

    nveg24_path = Path(CONFIG["paths"]["intersect_dir"]) / "SIMCAR_P_vegetacao_radambrasil_x_car_atp_nveg24.parquet"
    if nveg24_path.exists():
        rd = read_pq(nveg24_path)
        if "FITOECOLOG" in rd.columns:
            rd["FITOECOLOG"] = rd["FITOECOLOG"].astype(str).str.strip().str.upper()
            area = pd.to_numeric(rd.get("Shape_Area", 0), errors="coerce").fillna(0)
            rd["radam_forest_nveg24_ha"] = np.where(rd["FITOECOLOG"] == "FLORESTA", area, 0) / 10000
            rd["radam_cerrado_nveg24_ha"] = np.where(rd["FITOECOLOG"] == "CERRADO", area, 0) / 10000
            rd = rd.groupby(jk, as_index=False)[["radam_forest_nveg24_ha", "radam_cerrado_nveg24_ha"]].sum()
            rd["radam_total_nveg24_ha"] = rd["radam_forest_nveg24_ha"] + rd["radam_cerrado_nveg24_ha"]
            df = df.merge(rd, on=jk, how="left")

    added_cols = [c for c in df.columns if c not in set(original_cols + ["AREA_HA", "area_ha_car"])]
    df["size_class"] = df.get("MODULOS_FI", 0).map(make_size_class)
    denom = pd.to_numeric(df["area_ha_car"], errors="coerce").replace(0, np.nan)

    pct_data = {
        f"{col}_pct": pd.to_numeric(df[col], errors="coerce") / denom
        for col in added_cols
        if pd.api.types.is_numeric_dtype(df[col])
    }
    if pct_data:
        df = pd.concat([df, pd.DataFrame(pct_data, index=df.index)], axis=1)

    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].fillna(0)
    df = df.fillna(0)

    area_cols = [c for c in num_cols if c.endswith("_ha") and c not in {"area_ha_car", "AREA_HA", "overlap_ha"}]
    for col in area_cols:
        df[col] = np.minimum(np.maximum(pd.to_numeric(df[col], errors="coerce").fillna(0), 0), df["area_ha_car"])

    pct_cols = [c for c in df.columns if c.endswith("_pct")]
    for col in pct_cols:
        df[col] = np.minimum(pd.to_numeric(df[col], errors="coerce").fillna(0), 1)

    catalogue = pd.DataFrame({
        "col": df.columns,
        "class": [str(df[c].dtype) for c in df.columns],
        "source": ["CAR_ATP" if c in original_cols else "derived_pct" if c.endswith("_pct") else "derived" if c == "size_class" else "layer_join" for c in df.columns],
    })
    save_json(catalogue, "col_catalogue.json")
    return df, catalogue


def diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    print("\nSTEP 7: Checking pct columns > 100%...")
    # Values above 100% are generally geometric or attributional diagnostics,
    # not legal signals. They usually indicate overlapping source polygons,
    # duplicated joins, or denominator inconsistencies. They are checked here
    # explicitly because legal interpretation becomes unreliable when spatial
    # accounting exceeds the physical property area.
    rows = []
    pct_cols = [c for c in df.columns if c.endswith("_pct")]
    for col in pct_cols:
        vals = pd.to_numeric(df[col], errors="coerce")
        over = vals[vals > 1]
        if over.empty:
            continue
        rows.append({
            "col": col,
            "n_over100": int(over.shape[0]),
            "pct_of_total": round(100 * over.shape[0] / len(df), 2),
            "min_val": round(float(over.min()), 4),
            "max_val": round(float(over.max()), 4),
            "mean_val": round(float(over.mean()), 4),
            "has_inf": bool(np.isinf(vals).any()),
        })
    overflows = pd.DataFrame(rows)
    if overflows.empty:
        print("  [OK] No pct column exceeds 100%.")
        return overflows
    save_json(overflows, "overflow_cols.json")
    return overflows


def compute_forest_code_metrics(df: pd.DataFrame) -> pd.DataFrame:
    print("\nSTEP 8: Computing Forest Code metrics...")
    # Canonical historical cut-offs: net/max removes overlap double counting.
    # Both values are bounded to the physical CAR area before legal formulas.
    for year in (2000, 2008):
        selected = f"cons_area_{year}_net_max"
        canonical = f"cons_area_{year}"
        if selected in df.columns:
            values = pd.to_numeric(df[selected], errors="coerce").fillna(0)
        elif canonical in df.columns:
            values = pd.to_numeric(df[canonical], errors="coerce").fillna(0)
        else:
            raise KeyError(f"Required historical baseline missing: {canonical}")
        df[f"cons_area_{year}"] = np.minimum(
            values.clip(lower=0),
            pd.to_numeric(df["area_ha_car"], errors="coerce").fillna(0),
        )
    if "cons_area_2000_proxy" not in df.columns:
        df["cons_area_2000_proxy"] = df["cons_area_2000"]
    if "cons_area_2000_proxy_missing" not in df.columns:
        df["cons_area_2000_proxy_missing"] = False
    if "cons_area_2000_source" not in df.columns:
        df["cons_area_2000_source"] = "proxy_net_max"
    return forest_code_compliance(df, CONFIG)


def compute_block(d: pd.DataFrame) -> pd.Series:
    bool_cols = {
        "n_art67_small_prop": "art67_small_prop",
        "n_mt_special_mun": "mt_special_mun",
        "n_art68_exempt_forest": "art68_exempt_forest",
        "n_art68_exempt_cerrado": "art68_exempt_cerrado",
    }
    sum_cols_list = [
        "area_ha_car", "radam_total_ha", "radam_forest_ha", "radam_cerrado_ha",
        "rl_exist_forest_ha", "rl_exist_cerrado_ha", "rl_exist_total_ha",
        "rl_req_forest_ha", "rl_req_cerrado_ha", "rl_req_total_ha", "rl_req_uncapped_total_ha",
        "avail_ha", "rl_cap_ha", "rl_req_pre2000_forest_ha", "rl_req_pre2000_cerrado_ha",
        "rl_req_mt_forest_ha", "rl_gross_deficit_forest_ha", "rl_gross_deficit_cerrado_ha",
        "rl_gross_deficit_ha", "rl_surplus_forest_ha", "rl_surplus_cerrado_ha", "rl_surplus_total_ha",
        "rl_adj_deficit_forest_ha", "rl_adj_deficit_cerrado_ha", "rl_adj_deficit_ha",
        "rl_post2008_ha", "rl_restore_ha", "rl_compensate_ha", "app_req_ha", "app_preserved_ha",
        "app_gross_deficit_ha", "app_replant_raw_ha", "app_restore_auas_ha", "app_consolidated_ha",
        "app_consol_restore_ha", "app_restore_ha",
    ]
    out = {"n_total_car": int(len(d)), "n_valid_car": int((d["car_valid"] == True).sum())}
    for k, src in bool_cols.items():
        out[k] = int(d.get(src, pd.Series(False, index=d.index)).sum())
    for col in sum_cols_list:
        out["area_total_ha" if col == "area_ha_car" else col] = float(col_or_zero(d, col).sum())
    return pd.Series(out)


def build_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    print("\nSTEP 9: Building summary table...")
    active = df[df["car_valid"] == True].copy()
    inactive = df[df["car_valid"] != True].copy()

    def summarize_by_size(work: pd.DataFrame) -> pd.DataFrame:
        if work.empty:
            return pd.DataFrame(columns=["size_class", *compute_block(work).index.tolist()])
        rows = []
        for size_class, group in work.groupby("size_class", dropna=False, observed=True):
            row = compute_block(group).to_dict()
            row["size_class"] = size_class
            rows.append(row)
        return pd.DataFrame(rows)

    by_active = summarize_by_size(active)
    by_inactive = summarize_by_size(inactive)
    by_active["size_class"] = pd.Categorical(by_active["size_class"], SIZE_LEVELS, ordered=True)
    by_inactive["size_class"] = pd.Categorical(by_inactive["size_class"], SIZE_LEVELS, ordered=True)
    by_active = by_active.sort_values("size_class")
    by_inactive = by_inactive.sort_values("size_class")
    total_active = pd.DataFrame([compute_block(active)]).assign(size_class="Total (Active)")
    total_inactive = pd.DataFrame([compute_block(inactive)]).assign(size_class="Total (Inactive)")
    by_active["group"] = "Active"
    by_inactive["group"] = "Inactive"
    total_active["group"] = "Active"
    total_inactive["group"] = "Inactive"
    return pd.concat([by_active, total_active, by_inactive, total_inactive], ignore_index=True)


def validation_cases() -> pd.DataFrame:
    return pd.DataFrame([
        {"car_num": "MT100017/2021", "mun_code": "5107958", "biome_rl": "Amazônia - RL 50%", "has_digital": True, "o_atp": 163.2943, "d_atp": 163.2943},
        {"car_num": "MT194036/2020", "mun_code": "5106240", "biome_rl": "Amazônia - RL 80%", "has_digital": False, "o_atp": 321.5609, "d_atp": np.nan},
        {"car_num": "MT100490/2024", "mun_code": "5102686", "biome_rl": "Amazônia - Floresta + Cerrado", "has_digital": True, "o_atp": 441.6857, "d_atp": 441.6857},
    ])


def build_excel_outputs(df: pd.DataFrame, summary_table: pd.DataFrame, match_tbl: pd.DataFrame, car_summary: pd.DataFrame, catalogue: pd.DataFrame) -> Path:
    print("\nSTEP 10: Exporting Excel multi-tab...")
    # Use the pipeline's configured run date (paths.RUN_DATE), not the real
    # calendar date: downstream stages (_10_kernel.dated(), _20_build_priority.py,
    # etc.) all resolve "the current dataset" by this fixed date. Naming outputs
    # by date.today() instead orphans a re-run on a later calendar day into an
    # unused file while every consumer keeps silently reading the stale one.
    today = _paths.RUN_DATE
    excel_path = out_dir() / f"fc_summary_mt_{today}.xlsx"
    active = df[df["car_valid"] == True].copy()
    inactive = df[df["car_valid"] != True].copy()
    overview = pd.DataFrame([
        ["Total rural properties (n)", len(df), len(active), len(inactive)],
        ["Total property area (ha)", df["area_ha_car"].sum(), active["area_ha_car"].sum(), inactive["area_ha_car"].sum()],
        ["Required RL - total (ha)", col_or_zero(df, "rl_req_total_ha").sum(), col_or_zero(active, "rl_req_total_ha").sum(), col_or_zero(inactive, "rl_req_total_ha").sum()],
        ["Existing RL - total (ha)", col_or_zero(df, "rl_exist_total_ha").sum(), col_or_zero(active, "rl_exist_total_ha").sum(), col_or_zero(inactive, "rl_exist_total_ha").sum()],
        ["Adjusted RL deficit (ha)", col_or_zero(df, "rl_adj_deficit_ha").sum(), col_or_zero(active, "rl_adj_deficit_ha").sum(), col_or_zero(inactive, "rl_adj_deficit_ha").sum()],
        ["APP restore (ha)", col_or_zero(df, "app_restore_ha").sum(), col_or_zero(active, "app_restore_ha").sum(), col_or_zero(inactive, "app_restore_ha").sum()],
    ], columns=["Metric", "All CARs", "Active CARs", "Inactive CARs"])
    status_tbl = car_summary.copy()
    exemptions = pd.DataFrame([
        ["All active properties", len(active), 100.0, active["area_ha_car"].sum()],
        ["Art.67 exempt (<=4 MF)", int(active["art67_small_prop"].sum()), round(100 * active["art67_small_prop"].mean(), 1) if len(active) else 0, active.loc[active["art67_small_prop"], "area_ha_car"].sum()],
        ["Art.68 exempt - forest", int(active["art68_exempt_forest"].sum()), round(100 * active["art68_exempt_forest"].mean(), 1) if len(active) else 0, active.loc[active["art68_exempt_forest"], "area_ha_car"].sum()],
        ["Art.68 exempt - cerrado", int(active["art68_exempt_cerrado"].sum()), round(100 * active["art68_exempt_cerrado"].mean(), 1) if len(active) else 0, active.loc[active["art68_exempt_cerrado"], "area_ha_car"].sum()],
        ["MT special municipalities", int(active["mt_special_mun"].sum()), round(100 * active["mt_special_mun"].mean(), 1) if len(active) else 0, active.loc[active["mt_special_mun"], "area_ha_car"].sum()],
    ], columns=["Category", "Properties (n)", "% of Active (n)", "Area (ha)"])
    restore_cra = pd.DataFrame([
        ["Gross RL deficit", int((active["rl_gross_deficit_ha"] > 0).sum()), active["rl_gross_deficit_ha"].sum()],
        ["Adjusted RL deficit", int((active["rl_adj_deficit_ha"] > 0).sum()), active["rl_adj_deficit_ha"].sum()],
        ["Restore in-situ", int((active["rl_restore_ha"] > 0).sum()), active["rl_restore_ha"].sum()],
        ["CRA compensation", int((active["rl_compensate_ha"] > 0).sum()), active["rl_compensate_ha"].sum()],
        ["RL surplus", int((active["rl_surplus_total_ha"] > 0).sum()), active["rl_surplus_total_ha"].sum()],
    ], columns=["Item", "Properties (n)", "Area (ha)"])
    dict_sheet = catalogue.rename(columns={"col": "Column", "class": "Type", "source": "Source"}).assign(Description="")
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        overview.to_excel(writer, sheet_name="T0_Overview", index=False)
        status_tbl.to_excel(writer, sheet_name="T1_CAR_Status", index=False)
        summary_table.to_excel(writer, sheet_name="T2_RL_SizeClass", index=False)
        summary_table.to_excel(writer, sheet_name="T3_APP_SizeClass", index=False)
        exemptions.to_excel(writer, sheet_name="T4_Exemptions", index=False)
        restore_cra.to_excel(writer, sheet_name="T5_Restore_CRA", index=False)
        dict_sheet.to_excel(writer, sheet_name="T6_Dict", index=False)
        validation_cases().to_excel(writer, sheet_name="T7_Validation", index=False)
        df.to_excel(writer, sheet_name="T8_Raw", index=False)
    return excel_path


def save_outputs(df: pd.DataFrame, match_tbl: pd.DataFrame, summary_table: pd.DataFrame, excel_path: Path) -> dict[str, Path]:
    print("\nSTEP 11: Saving outputs...")
    # See the note in build_excel_outputs() above: must match paths.RUN_DATE, not
    # today's real calendar date, or downstream stages silently keep reading the
    # previous run's files instead of this one.
    today = _paths.RUN_DATE
    csv_path = out_dir() / f"car_atp_joined_{today}.csv"
    pq_path = out_dir() / f"car_atp_joined_{today}.parquet"
    mt_path = out_dir() / f"match_table_{today}.csv"
    st_path = out_dir() / f"summary_table_{today}.csv"
    df.to_csv(csv_path, index=False)
    # Notebook execution order can occasionally leave helper definitions out of
    # sync with downstream cells after edits or partial reruns. To keep the
    # export step robust, we fall back to a local copy of the Parquet-safety
    # normalization if the global helper is not available in the active kernel.
    parquet_safe_fn = globals().get("make_parquet_safe")
    if parquet_safe_fn is None:
        def parquet_safe_fn(local_df: pd.DataFrame) -> pd.DataFrame:
            safe = local_df.copy()
            for col in safe.select_dtypes(include=["object"]).columns:
                non_null = safe[col].dropna()
                if non_null.empty:
                    safe[col] = safe[col].astype("string")
                    continue
                py_types = non_null.map(lambda x: type(x).__name__).unique().tolist()
                if len(py_types) > 1:
                    safe[col] = safe[col].astype("string")
            return safe
    parquet_safe_fn(df).to_parquet(pq_path, index=False)
    match_tbl.to_csv(mt_path, index=False)
    summary_table.to_csv(st_path, index=False)
    return {"excel_path": excel_path, "csv_path": csv_path, "pq_path": pq_path, "match_table_path": mt_path, "summary_table_path": st_path}


def run_fc_summary_mt() -> dict[str, Any]:
    layers_meta = discover_layers()
    car, car_summary = load_car()
    save_summary_plot(car)
    layer_list, read_log = read_layers(layers_meta)
    layer_list, dissolve_check = dissolve_layers(layer_list, car)
    match_tbl = build_match_table(layer_list, car)
    validate_exhaustive_intersections(match_tbl)
    df, catalogue = join_layers(car, layer_list)
    overflows = diagnostics(df)
    df = compute_forest_code_metrics(df)
    summary_table = build_summary_table(df)
    excel_path = build_excel_outputs(df, summary_table, match_tbl, car_summary, catalogue)
    outputs = save_outputs(df, match_tbl, summary_table, excel_path)
    return {
        "layers_meta": layers_meta,
        "car": car,
        "car_summary": car_summary,
        "read_log": read_log,
        "dissolve_check": dissolve_check,
        "match_tbl": match_tbl,
        "df": df,
        "catalogue": catalogue,
        "overflows": overflows,
        "summary_table": summary_table,
        "outputs": outputs,
    }


if __name__ == "__main__":
    run_fc_summary_mt()
