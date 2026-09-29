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

VALIDADO_ROOT = RAW_DIR / "simcar_validado"
VALIDADO_CAR_ATP = VALIDADO_ROOT / "CAR_ATP.parquet"
VALIDADO_INTERSECT_DIR = VALIDADO_ROOT
VALIDADO_OUTPUT_DIR = PREPROCESSED_DIR / "car_validated"


base.CONFIG["paths"]["car_atp"] = VALIDADO_CAR_ATP
base.CONFIG["paths"]["intersect_dir"] = VALIDADO_INTERSECT_DIR
base.CONFIG["paths"]["output_dir"] = VALIDADO_OUTPUT_DIR
base.CONFIG["radam_label"] = "VEGETACAO_RADAMBRASIL"
base.CONFIG["nveg_radam_label"] = "__not_available_in_simcar_validado__"
base.CONFIG["fitoecolog_col"] = "lyr_FITOECOLOG"


LAYER_NAME_MAP = {
    "CAR_APP": "app",
    "CAR_APPD": "appd_declared_ha",
    "CAR_APPRL": "apprl_declared_ha",
    "CAR_ARL": "arl_declared_ha",
    "CAR_AU": "au_declared_ha",
    "CAR_AUAS": "auas_post2008",
    "CAR_AVN": "avn_declared_ha",
    "CAR_NASCENTE": "nascente",
    "SIMCAR_ARLD": "arld_declared_ha",
    "SIMCAR_CAR_AREA_CONSOLIDADA": "cons_area_2000",
    "SIMCAR_CAR_UTILIDADE_PUBLICA": "utilidade_publica",
}


def read_pq(path: str | Path, columns: list[str] | None = None) -> pd.DataFrame:
    if columns is None:
        return _base_read_pq(path)
    import pyarrow.parquet as pq

    available = pq.ParquetFile(path).schema_arrow.names
    use_cols = [col for col in columns if col in available]
    return pd.read_parquet(path, columns=use_cols)


def add_validado_car_join(df: pd.DataFrame) -> pd.DataFrame:
    if base.CONFIG["join_key"] in df.columns:
        return df
    if "prop_id_unique" not in df.columns:
        return df
    df = df.copy()
    df[base.CONFIG["join_key"]] = df["prop_id_unique"].astype("string")
    return df


def read_sum(path: str | Path, out_col: str) -> pd.DataFrame:
    df = add_validado_car_join(read_pq(path, ["car_join", "prop_id_unique", "area_ha"]))
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
    df = add_validado_car_join(read_pq(path, ["car_join", "prop_id_unique", fito, "area_ha"]))
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
    print("STEP 1: Discovering SIMCAR validado intersect parquets...")
    rows: list[dict[str, Any]] = []
    for path in sorted(Path(base.CONFIG["paths"]["intersect_dir"]).glob("*.parquet")):
        label = path.stem.removesuffix("_x_car_atp")
        is_radam = label == base.CONFIG["radam_label"]
        rows.append(
            {
                "path": str(path),
                "label": label,
                "short": LAYER_NAME_MAP.get(label, label.lower()),
                "is_radam": is_radam,
                "is_nveg_radam": False,
                "type": "RADAM" if is_radam else "validado_declared",
            }
        )
    if not rows:
        raise FileNotFoundError("No parquet files found in SIMCAR validado intersect_dir.")
    base.save_json(rows, "layers_meta.json")
    base.save_json(
        {
            "source": "simcar_validado",
            "car_atp": base.CONFIG["paths"]["car_atp"],
            "intersect_dir": base.CONFIG["paths"]["intersect_dir"],
            "requested_source_dir": str(VALIDADO_ROOT / "01_parquet"),
            "layer_name_map": LAYER_NAME_MAP,
            "join_key": "prop_id_unique copied to car_join",
            "rl_existing_proxy": "CAR_ARL allocated to RADAM forest/cerrado proportions",
            "appd_proxy": "single CAR_APPD layer copied into all size-class APPD inputs used by the base rule",
            "note": "The 01_parquet folder contains source layers; this script uses the matching 02_output/intersect products already present for those validated CAR layers.",
        },
        "validado_adaptation_notes.json",
    )
    return pd.DataFrame(rows)


def load_car() -> tuple[pd.DataFrame, pd.DataFrame]:
    print("\nSTEP 2: Loading SIMCAR validado CAR_ATP...")
    jk = base.CONFIG["join_key"]
    car = read_pq(base.CONFIG["paths"]["car_atp"]).copy()
    if "prop_id_unique" not in car.columns:
        raise KeyError("'prop_id_unique' not found in SIMCAR validado CAR_ATP.")
    car[jk] = car["prop_id_unique"].astype("string")
    car["CODIGO_CAR"] = car.get("CAR_FEDERA", "").astype(str)
    car["SITUACAO"] = car.get("SITUACAO_C", "").astype(str)
    car["mun_geocodigo"] = base.derive_municipality_code(car)
    car["car_valid"] = ~car["SITUACAO"].map(base.is_invalid)
    car["status_rank"] = car["SITUACAO"].map(base.get_rank)
    car["area_ha_car"] = pd.to_numeric(car.get("AREA_HA", 0), errors="coerce").fillna(0)
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
    total_row = pd.DataFrame([{"car_valid": None, "SITUACAO": "Total", "status_rank": None, "n": total_n, "area_ha_car": total_area, "pct_n": 100.0, "pct_area": 100.0}])
    base.save_json(pd.concat([summary, total_row], ignore_index=True), "car_summary.json")
    return car, summary


FULL_COVERAGE_RADAM = PACKAGE_ROOT / "data" / "proc" / "simcar_validado" / "radam_full_coverage_x_car_atp.parquet"
FULL_COVERAGE_NVEG24 = PACKAGE_ROOT / "data" / "proc" / "simcar_validado" / "radam_nveg24_full_coverage.parquet"


def read_layers(layers_meta: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    print("\nSTEP 3: Reading SIMCAR validado intersect layers...")
    layer_list: dict[str, pd.DataFrame] = {}
    read_log: list[dict[str, Any]] = []
    for idx, row in layers_meta.reset_index(drop=True).iterrows():
        print(f"  [{idx + 1}/{len(layers_meta)}] {row['label']} -> {row['short']}")
        try:
            if row["is_radam"]:
                # Do not use the legacy CAR-clipped product here: it contains
                # only the subset intersected in the old validated universe.
                # The authoritative statewide RADAM is consumed through the
                # independently rebuilt full-coverage product below.
                read_log.append({"label": row["label"], "status": "REJECTED_PARTIAL", "key": "radam", "rows": 0})
            else:
                data = read_sum(row["path"], out_col=row["short"])
                layer_list[row["short"]] = data
                read_log.append({"label": row["label"], "status": "OK", "key": row["short"], "rows": len(data)})
        except Exception as exc:
            read_log.append({"label": row["label"], "status": "ERROR", "key": row["short"], "message": str(exc)})

    # AUD-013 fix: data/raw/simcar_validado/VEGETACAO_RADAMBRASIL_x_car_atp.parquet
    # (picked up above) only intersects ~30% of validado properties (12,485 of
    # 41,696), so radam_total_ha collapses to 0 - and therefore BOTH the RL
    # requirement and the RL existing-vegetation allocation - for the other
    # 70%. This overrides it with an independently computed, full-coverage
    # RADAM x property intersection (see the project audit trail
    # AUD-013 for the raster-based methodology and validation against 12 real
    # SIMCAR control CARs). Left in data/proc/, not data/raw/: it is a derived
    # product, not a declared/raw CAR input.
    if not FULL_COVERAGE_RADAM.exists():
        raise FileNotFoundError(f"Required full-coverage RADAM intersection not found: {FULL_COVERAGE_RADAM}")
    data = read_fito(FULL_COVERAGE_RADAM, prefix="radam")
    if data is None:
        raise RuntimeError(f"Invalid full-coverage RADAM intersection: {FULL_COVERAGE_RADAM}")
    layer_list["radam"] = data
    read_log.append({"label": "radam_full_coverage_independent", "status": "OK", "key": "radam", "rows": len(data)})
    print(f"  [authoritative] full-coverage RADAM intersection applied ({len(data)} properties)")

    read_log_df = pd.DataFrame(read_log)
    base.save_json(read_log_df, "read_log.json")
    return layer_list, read_log_df


def join_layers(car: pd.DataFrame, layer_list: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    df, catalogue = _base_join_layers(car, layer_list)

    # AUD-013 fix: existing native vegetation ("what's actually still standing")
    # used to be estimated by allocating the CAR-declared arl_declared_ha
    # proportionally by RADAM forest:cerrado ratio - which (a) is derived from a
    # self-reported CAR figure rather than an independent measurement, and (b)
    # collapsed to 0 whenever radam_total_ha was 0 (see the old logic this
    # replaced and preserved in the project audit trail
    # AUD-013). It is now taken directly from an independently computed
    # RADAM x PRODES-2024-native-vegetation intersection (same methodology the
    # proxy source already used via SIMCAR_P_..._nveg24.parquet - see
    # code/preprocess/_10_preprocess_proxy.py), with no CAR-declared input at all.
    jk = base.CONFIG["join_key"]
    if FULL_COVERAGE_NVEG24.exists():
        nveg = pd.read_parquet(FULL_COVERAGE_NVEG24)
        key_col = "prop_id_unique" if "prop_id_unique" in nveg.columns else "car_join"
        nveg = nveg.rename(columns={key_col: jk})
        nveg[jk] = nveg[jk].astype("string")
        df = df.merge(nveg, on=jk, how="left")
        for col in ("radam_forest_nveg24_ha", "radam_cerrado_nveg24_ha", "radam_total_nveg24_ha"):
            df[col] = pd.to_numeric(df.get(col), errors="coerce").fillna(0.0)

    if "appd_declared_ha" in df.columns:
        for col in ("appd_lte1mf_cs08", "appd_1a2mf_cs08", "appd_2a4mf_cs08", "appd_4a10mf_cs08", "appd_gt10mf_cs08"):
            df[col] = base.col_or_zero(df, "appd_declared_ha")

    return df, catalogue


def compute_forest_code_metrics(df: pd.DataFrame) -> pd.DataFrame:
    # AUD-013 fix: rl_exist_forest_ha/rl_exist_cerrado_ha (and everything
    # downstream: gross/adjusted deficit, surplus, Art.68 exemption, restore/
    # compensate) used to be recomputed here from arl_declared_ha - a
    # CAR-declared figure - overwriting the already-correct, independently
    # computed values that _base_compute_forest_code_metrics() (in
    # code/_11_forest_code_compliance.py) derives from radam_forest_nveg24_ha /
    # radam_cerrado_nveg24_ha (now populated in join_layers() from the
    # independent RADAM x PRODES-2024 intersection, see AUD-013). No override
    # is needed any more: the base function's calculation is used as-is.
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
base.load_car = load_car
base.read_layers = read_layers
base.join_layers = join_layers
base.compute_forest_code_metrics = compute_forest_code_metrics


def run_fc_summary_mt_validado() -> dict[str, Any]:
    return base.run_fc_summary_mt()


if __name__ == "__main__":
    run_fc_summary_mt_validado()
