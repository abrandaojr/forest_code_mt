from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


BASE_SCRIPT = Path(__file__).with_name("_10_preprocess_proxy.py")
spec = importlib.util.spec_from_file_location("fc_summary_mt_base", BASE_SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load base script: {BASE_SCRIPT}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


_base_read_pq = base.read_pq
_base_join_layers = base.join_layers
_base_compute_forest_code_metrics = base.compute_forest_code_metrics


PACKAGE_ROOT = Path(os.environ.get("FCM_ROOT", Path(__file__).resolve().parents[3]))
RAW_DIR = Path(os.environ.get("FCM_RAW_DIR", PACKAGE_ROOT / "data" / "raw"))
PREPROCESSED_DIR = Path(os.environ.get("FCM_PREPROCESSED_DIR", PACKAGE_ROOT / "data" / "pre"))

DIGITAL_INTERSECT_DIR = RAW_DIR / "simcar_digital"
DIGITAL_OUTPUT_DIR = PREPROCESSED_DIR / "car_digital"


base.CONFIG["paths"]["intersect_dir"] = DIGITAL_INTERSECT_DIR
base.CONFIG["paths"]["output_dir"] = DIGITAL_OUTPUT_DIR
base.CONFIG["radam_label"] = "VEGETACAO_RADAMBRASIL"
base.CONFIG["nveg_radam_label"] = "__not_available_in_simcar_digital__"
base.CONFIG["fitoecolog_col"] = "lyr_FITOECOLOG"


LAYER_NAME_MAP = {
    "SIMCAR_D_APP": "app",
    "SIMCAR_D_APPD_ATE1MF_AC": "appd_lte1mf_cs08",
    "SIMCAR_D_APPD_1A2MF_AC": "appd_1a2mf_cs08",
    "SIMCAR_D_APPD_2A4MF_AC": "appd_2a4mf_cs08",
    "SIMCAR_D_APPD_4A10MF_AC": "appd_4a10mf_cs08",
    "SIMCAR_D_APPD_MAIOR_10MF_AC": "appd_gt10mf_cs08",
    "SIMCAR_D_APPD_AUAS": "app_fnl_auas",
    "SIMCAR_D_AREA_CONSOLIDADA": "cons_area_2000",
    "SIMCAR_D_ARL": "arl_declared_ha",
    "SIMCAR_D_AUAS": "auas_post2008",
    "SIMCAR_D_AVN": "avn_declared_ha",
}


def read_pq(path: str | Path, columns: list[str] | None = None) -> pd.DataFrame:
    if columns is None:
        return _base_read_pq(path)
    import pyarrow.parquet as pq

    available = pq.ParquetFile(path).schema_arrow.names
    use_cols = [col for col in columns if col in available]
    return pd.read_parquet(path, columns=use_cols)


def add_digital_car_join(df: pd.DataFrame) -> pd.DataFrame:
    if base.CONFIG["join_key"] in df.columns:
        return df
    if "car_OBJECTID" not in df.columns:
        return df
    df = df.copy()
    object_id = pd.to_numeric(df["car_OBJECTID"], errors="coerce").astype("Int64")
    df[base.CONFIG["join_key"]] = "car_" + object_id.astype("string")
    df.loc[object_id.isna(), base.CONFIG["join_key"]] = pd.NA
    return df


def read_sum(path: str | Path, out_col: str) -> pd.DataFrame:
    df = add_digital_car_join(read_pq(path, ["car_join", "car_OBJECTID", "prop_id_unique", "area_ha"]))
    if "area_ha" not in df.columns:
        print(f"  [WARN] area_ha not found in {Path(path).name}; writing zero-area layer")
        df["area_ha"] = 0.0
    key = base.best_key(df)
    return (
        df.groupby(key, as_index=False)["area_ha"]
        .sum()
        .rename(columns={key: base.CONFIG["join_key"], "area_ha": out_col})
    )


def read_fito(path: str | Path, prefix: str) -> pd.DataFrame | None:
    fito = base.CONFIG["fitoecolog_col"]
    df = add_digital_car_join(read_pq(path, ["car_join", "car_OBJECTID", "prop_id_unique", fito, "area_ha"]))
    key = base.best_key(df)
    if fito not in df.columns:
        print(f"  [WARN] {fito} not found in {Path(path).name}")
        return None
    work = df[[key, fito, "area_ha"]].copy()
    work[fito] = work[fito].astype(str).str.strip().str.upper()
    agg = work.groupby([key, fito], as_index=False)["area_ha"].sum()
    wide = agg.pivot_table(index=key, columns=fito, values="area_ha", fill_value=0, aggfunc="sum").reset_index()
    wide.columns = [col if col == key else f"{prefix}_{col}_ha" for col in wide.columns]
    return wide.rename(columns={key: base.CONFIG["join_key"]})


def discover_layers() -> pd.DataFrame:
    print("STEP 1: Discovering SIMCAR digital intersect parquets...")
    rows: list[dict[str, Any]] = []
    for path in sorted(Path(base.CONFIG["paths"]["intersect_dir"]).glob("*.parquet")):
        label = path.stem.removesuffix("_x_car_atp")
        is_radam = label == base.CONFIG["radam_label"]
        rows.append(
            {
                "path": str(path),
                "label": label,
                "short": LAYER_NAME_MAP.get(label, label.removeprefix("SIMCAR_D_").lower()),
                "is_radam": is_radam,
                "is_nveg_radam": False,
                "type": "RADAM" if is_radam else "digital_declared",
            }
        )
    if not rows:
        raise FileNotFoundError("No parquet files found in SIMCAR digital intersect_dir.")
    base.save_json(rows, "layers_meta.json")
    base.save_json(
        {
            "source": "simcar_digital",
            "intersect_dir": base.CONFIG["paths"]["intersect_dir"],
            "layer_name_map": LAYER_NAME_MAP,
            "rl_existing_proxy": "SIMCAR_D_ARL allocated to RADAM forest/cerrado proportions",
            "app_restore_proxy": "SIMCAR_D_APPD_*_AC and SIMCAR_D_APPD_AUAS declared digital layers",
            "note": "Digital source does not include proxy-only native_veg_x_radam/app_fnl_avn24 layers.",
        },
        "digital_adaptation_notes.json",
    )
    return pd.DataFrame(rows)


# AUD-013 fix: the "digital" property universe (loaded via load_car(), inherited
# unmodified from _10_preprocess_proxy.py since this script never overrides
# CONFIG["paths"]["car_atp"]) is data/raw/simcar_requerido/CAR_ATP.parquet -
# the EXACT same 176,020-property set (same car_join keys) that the proxy
# source uses. The proxy source already has a correct, fully-vector (no
# raster, no dissolve needed), per-property RADAM x FITOECOLOG intersection
# for that same property set - data/raw/simcar_proxy/
# SIMCAR_P_vegetacao_radambrasil_x_car_atp.parquet (required-side) and
# SIMCAR_P_vegetacao_radambrasil_x_car_atp_nveg24.parquet (existing-vegetation
# side, independent of any CAR declaration). Verified 100% of car_join keys
# match. So "digital" simply borrows these already-correct files directly -
# no new geoprocessing needed for this source.
PROXY_RADAM_FILE = RAW_DIR / "simcar_proxy" / "SIMCAR_P_vegetacao_radambrasil_x_car_atp.parquet"
PROXY_NVEG24_FILE = RAW_DIR / "simcar_proxy" / "SIMCAR_P_vegetacao_radambrasil_x_car_atp_nveg24.parquet"


def read_layers(layers_meta: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    print("\nSTEP 3: Reading SIMCAR digital intersect layers...")
    layer_list: dict[str, pd.DataFrame] = {}
    read_log: list[dict[str, Any]] = []
    for idx, row in layers_meta.reset_index(drop=True).iterrows():
        print(f"  [{idx + 1}/{len(layers_meta)}] {row['label']} -> {row['short']}")
        try:
            if row["is_radam"]:
                data = read_fito(row["path"], prefix="radam")
                if data is not None:
                    layer_list["radam"] = data
                read_log.append({"label": row["label"], "status": "OK", "key": "radam", "rows": 0 if data is None else len(data)})
            else:
                data = read_sum(row["path"], out_col=row["short"])
                layer_list[row["short"]] = data
                read_log.append({"label": row["label"], "status": "OK", "key": row["short"], "rows": len(data)})
        except Exception as exc:
            read_log.append({"label": row["label"], "status": "ERROR", "key": row["short"], "message": str(exc)})

    # AUD-013 fix: data/raw/simcar_digital/VEGETACAO_RADAMBRASIL_x_car_atp.parquet
    # only intersects a minority of the digital property universe (the digital
    # source actually spans all of data/raw/simcar_requerido/CAR_ATP.parquet,
    # 176,020 properties - the base load_car() inherited from
    # _10_preprocess_proxy.py), so radam_total_ha collapses to 0 for ~71% of
    # rows - zeroing both the RL requirement and the RL existing-vegetation
    # allocation for them. Overridden here by borrowing the proxy source's own
    # already-correct, fully-vector RADAM x FITOECOLOG intersection for the
    # identical property set (see PROXY_RADAM_FILE note above / AUD-013).
    if PROXY_RADAM_FILE.exists():
        raw = pd.read_parquet(PROXY_RADAM_FILE, columns=["car_join", "FITOECOLOG", "area_ha"])
        raw["FITOECOLOG"] = raw["FITOECOLOG"].astype(str).str.strip().str.upper()
        agg = raw.groupby(["car_join", "FITOECOLOG"], as_index=False)["area_ha"].sum()
        wide = agg.pivot_table(index="car_join", columns="FITOECOLOG", values="area_ha", fill_value=0, aggfunc="sum").reset_index()
        wide.columns = [c if c == "car_join" else f"radam_{c}_ha" for c in wide.columns]
        layer_list["radam"] = wide
        read_log.append({"label": "radam_from_proxy_shared_universe", "status": "OK", "key": "radam", "rows": len(wide)})
        print(f"  [override] RADAM intersection borrowed from proxy's shared property universe ({len(wide)} properties)")

    read_log_df = pd.DataFrame(read_log)
    base.save_json(read_log_df, "read_log.json")
    return layer_list, read_log_df


def join_layers(car: pd.DataFrame, layer_list: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    df, catalogue = _base_join_layers(car, layer_list)

    # AUD-013 fix: existing native vegetation is now taken from the proxy
    # source's own already-correct, fully-vector RADAM x PRODES-2024-native-
    # vegetation intersection (same shared property universe, see
    # PROXY_NVEG24_FILE note above) instead of allocating the CAR-declared
    # arl_declared_ha by RADAM ratio (which also collapsed to 0 whenever
    # radam_total_ha was 0).
    jk = base.CONFIG["join_key"]
    if PROXY_NVEG24_FILE.exists():
        nv = pd.read_parquet(PROXY_NVEG24_FILE, columns=["car_join", "FITOECOLOG", "Shape_Area"])
        nv["FITOECOLOG"] = nv["FITOECOLOG"].astype(str).str.strip().str.upper()
        area = pd.to_numeric(nv["Shape_Area"], errors="coerce").fillna(0)
        nv["radam_forest_nveg24_ha"] = np.where(nv["FITOECOLOG"] == "FLORESTA", area, 0) / 10000
        nv["radam_cerrado_nveg24_ha"] = np.where(nv["FITOECOLOG"] == "CERRADO", area, 0) / 10000
        nveg = nv.groupby("car_join", as_index=False)[["radam_forest_nveg24_ha", "radam_cerrado_nveg24_ha"]].sum()
        nveg["radam_total_nveg24_ha"] = nveg["radam_forest_nveg24_ha"] + nveg["radam_cerrado_nveg24_ha"]
        nveg = nveg.rename(columns={"car_join": jk})
        nveg[jk] = nveg[jk].astype("string")
        df = df.merge(nveg, on=jk, how="left")
        for col in ("radam_forest_nveg24_ha", "radam_cerrado_nveg24_ha", "radam_total_nveg24_ha"):
            df[col] = pd.to_numeric(df.get(col), errors="coerce").fillna(0.0)

    return df, catalogue


def compute_forest_code_metrics(df: pd.DataFrame) -> pd.DataFrame:
    # AUD-013 fix: see the identical note in code/preprocess/_12_preprocess_validated.py.
    # rl_exist_forest_ha/rl_exist_cerrado_ha and everything downstream are no
    # longer overridden from arl_declared_ha; _base_compute_forest_code_metrics()
    # already derives them correctly from radam_forest_nveg24_ha /
    # radam_cerrado_nveg24_ha, now populated independently in join_layers().
    # AREA_CONSOLIDADA is the official 2008 consolidated-area layer. Keep the
    # legacy cons_area_2000 alias for backward-compatible scenario formulas,
    # but also expose the semantically correct field in every downstream file.
    df["cons_area_2008"] = base.col_or_zero(df, "cons_area_2000")
    df = _base_compute_forest_code_metrics(df)

    df["app_preserved_ha"] = np.minimum(base.col_or_zero(df, "avn_declared_ha"), df["app_req_ha"])
    df["app_gross_deficit_ha"] = np.maximum(df["app_req_ha"] - df["app_preserved_ha"], 0)
    df["app_consolidated_ha"] = np.minimum(base.col_or_zero(df, "cons_area_2000"), df["app_req_ha"])
    df["app_consol_restore_ha"] = np.minimum.reduce(
        [df["app_replant_raw_ha"], df["app_consolidated_ha"], df["app_gross_deficit_ha"]]
    )
    df["app_restore_ha"] = np.minimum.reduce(
        [df["app_consol_restore_ha"] + df["app_restore_auas_ha"], df["app_gross_deficit_ha"], df["app_cap_ha"]]
    )
    return df


base.read_pq = read_pq
base.read_sum = read_sum
base.read_fito = read_fito
base.discover_layers = discover_layers
base.read_layers = read_layers
base.join_layers = join_layers
base.compute_forest_code_metrics = compute_forest_code_metrics


def run_fc_summary_mt_digital() -> dict[str, Any]:
    return base.run_fc_summary_mt()


if __name__ == "__main__":
    run_fc_summary_mt_digital()
