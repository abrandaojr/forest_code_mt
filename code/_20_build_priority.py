from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

import _00_paths as paths
import _10_kernel as kernel

paths.set_env()
ROOT = paths.ROOT
PREPROCESSED_DIR = paths.PRE
OUT_DIR = paths.TABLES
OUT_DIR.mkdir(parents=True, exist_ok=True)


def latest_car_atp(folder: str) -> Path:
    candidates = sorted((PREPROCESSED_DIR / folder).glob("car_atp_joined_*.parquet"))
    if not candidates:
        return PREPROCESSED_DIR / folder / "car_atp_joined_YYYYMMDD.parquet"
    return candidates[-1]


INPUTS = {
    "simcar_validado": latest_car_atp(paths.CAR_PRE["simcar_validado"]),
    "simcar_digital": latest_car_atp(paths.CAR_PRE["simcar_digital"]),
    "simcar_proxy": latest_car_atp(paths.CAR_PRE["simcar_proxy"]),
}

SOURCE_ORDER = kernel.SOURCE_ORDER
SOURCE_PRIORITY = {source: i + 1 for i, source in enumerate(SOURCE_ORDER)}
SOURCE_LABELS = kernel.SOURCE_LABELS

ID_COLS = [
    "car_join", "prop_id_unique", "CODIGO_CAR", "CAR_FEDERA", "car_code",
    "NUMEROESTA", "NOMESPROPR", "NOMEPROPRI", "PROTOCOLO", "SITUACAO",
    "SITUACAO_C", "MUNICIPIO_", "mun_geocodigo", "MODULOS_FI", "AREA_HA",
    "area_ha_car", "car_valid", "status_rank", "size_class",
    "cons_area_2000_source",
]

METRIC_COLS = [
    "radam_forest_ha", "radam_cerrado_ha", "radam_total_ha",
    "radam_FLORESTA_ha", "radam_CERRADO_ha",
    "radam_forest_nveg24_ha", "radam_cerrado_nveg24_ha",
    "rl_req_forest_ha", "rl_req_cerrado_ha", "rl_req_total_ha",
    "rl_exist_forest_ha", "rl_exist_cerrado_ha", "rl_exist_total_ha",
    "rl_gross_deficit_forest_ha", "rl_gross_deficit_cerrado_ha",
    "rl_gross_deficit_ha", "rl_surplus_forest_ha", "rl_surplus_cerrado_ha",
    "rl_surplus_total_ha", "rl_adj_deficit_forest_ha",
    "rl_adj_deficit_cerrado_ha", "rl_adj_deficit_ha", "rl_post2008_ha",
    "rl_restore_ha", "rl_compensate_ha",
    "app", "app_req_ha", "app_preserved_ha", "app_gross_deficit_ha",
    "app_restore_ha", "app_replant_raw_ha", "app_consolidated_ha",
    "app_consol_restore_ha", "app_restore_auas_ha", "cons_area_2000",
    "cons_area_2008", "cons_area_2000_proxy", "cons_area_2000_proxy_missing",
    "veg_2000_ha", "veg_2008_ha", "req_teto_art12_ha", "req_piso_art68_ha",
    "rl_req_art67_ha", "rl_req_art68_ha", "rl_req_base_ha", "art68_legal_2000",
    "app_fnl_cs08", "app_fnl_auas", "app_fnl_avn24", "auas_post2008", "app_cap_ha",
    "appd_lte1mf_cs08", "appd_1a2mf_cs08", "appd_2a4mf_cs08",
    "appd_4a10mf_cs08", "appd_gt10mf_cs08",
    "rl_req_uncapped_forest_ha", "rl_req_uncapped_cerrado_ha",
    "rl_req_uncapped_total_ha", "rl_req_pre2000_forest_ha",
    "rl_req_pre2000_cerrado_ha", "rl_req_mt_forest_ha",
    "art67_small_prop", "mt_special_mun", "art68_exempt_forest",
    "art68_exempt_cerrado", "overlap_pct", "overlap_high",
    "arl_declared_ha", "avn_declared_ha", "appd_declared_ha",
    "apprl_declared_ha", "au_declared_ha", "utilidade_publica",
    "area_declividade", "area_inundada", "area_topo_morro",
    "area_umida", "borda_chapada", "interesse_social",
    "lagoa_natural", "manguezal", "nascente",
    "reservatorio_artificial", "restinga", "rio_10_a_50",
    "quilombolas", "quilombolas_x_car_atp_fnl",
    "terras_indigenas", "terras_indigenas_x_car_atp_fnl",
    "unidades_conservacao", "unidades_conservacao_x_car_atp_fnl",
    "assentamentos", "assentamentos_x_car_atp_fnl",
    "assentamentos_intermat", "assentamentos_intermat_x_car_atp_fnl",
]

CANONICAL_NUMERIC = [
    "area_ha_car", "MODULOS_FI", "radam_forest_ha", "radam_cerrado_ha",
    "radam_total_ha", "rl_req_total_ha", "rl_exist_total_ha",
    "rl_gross_deficit_ha", "rl_surplus_total_ha", "rl_adj_deficit_ha",
    "rl_post2008_ha", "rl_restore_ha", "rl_compensate_ha", "app_req_ha",
    "app_preserved_ha", "app_gross_deficit_ha", "app_restore_ha",
    "cons_area_2000", "cons_area_2008", "cons_area_2000_proxy", "veg_2000_ha", "veg_2008_ha",
    "req_teto_art12_ha", "req_piso_art68_ha", "rl_req_art67_ha", "rl_req_art68_ha", "rl_req_base_ha",
    "app_consolidated_ha", "app_consol_restore_ha",
    "app_restore_auas_ha", "app_cap_ha",
    "calc_gross_deficit_total_ha",
    "calc_deficit_total_ha",
]


def available_columns(path: Path) -> list[str]:
    return pq.ParquetFile(path).schema_arrow.names


def read_existing_columns(path: Path, wanted: Iterable[str]) -> pd.DataFrame:
    cols = available_columns(path)
    selected = [c for c in wanted if c in cols]
    return pd.read_parquet(path, columns=selected)


def first_nonblank(df: pd.DataFrame, candidates: Iterable[str]) -> pd.Series:
    out = pd.Series(pd.NA, index=df.index, dtype="object")
    for col in candidates:
        if col not in df.columns:
            continue
        val = df[col].astype("string").str.strip()
        val = val.mask(val.isin(["", "0", "nan", "NaN", "<NA>"]))
        out = out.where(out.notna(), val)
    return out


def num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def apply_source_order(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "input_file_type" in out.columns:
        out["input_file_type"] = pd.Categorical(
            out["input_file_type"].astype(str),
            categories=SOURCE_ORDER,
            ordered=True,
        )
    return out


def ordered_input_counts(series: pd.Series) -> pd.Series:
    return series.astype(str).value_counts().reindex(SOURCE_ORDER, fill_value=0)


def boolish(df: pd.DataFrame, col: str, default: bool = False) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index)
    s = df[col]
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(default)
    return s.astype("string").str.lower().isin(["true", "1", "yes", "sim"])


def clean_municipality_code(value) -> str | None:
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
    out = pd.Series(pd.NA, index=df.index, dtype="string")
    for col in ["mun_geocodigo", "MUNICIPIO_", "CODIGO_CAR", "CAR_FEDERA", "car_code", "NUMEROESTA"]:
        if col not in df.columns:
            continue
        codes = df[col].map(clean_municipality_code).astype("string")
        out = out.where(out.notna(), codes)
    return out.mask(out.str.fullmatch(r"0+").fillna(False))


def normalize_source(df: pd.DataFrame, source: str, path: Path) -> pd.DataFrame:
    df = df.copy()
    df["input_file_type"] = source
    df["input_priority"] = SOURCE_PRIORITY[source]
    df["input_file"] = str(path)

    df["property_code"] = first_nonblank(df, ["CODIGO_CAR", "CAR_FEDERA", "car_code"])
    df["property_code_norm"] = df["property_code"].astype("string").str.upper().str.strip()
    df["property_join_key"] = first_nonblank(df, ["car_join", "prop_id_unique"])
    fallback = "NO_CAR_CODE|" + source + "|" + df["property_join_key"].astype("string").fillna("")
    df["priority_key"] = df["property_code_norm"].where(df["property_code_norm"].notna(), fallback)

    if "SITUACAO" not in df.columns and "SITUACAO_C" in df.columns:
        df["SITUACAO"] = df["SITUACAO_C"]
    if "area_ha_car" not in df.columns:
        df["area_ha_car"] = num(df, "AREA_HA")
    if "radam_forest_ha" not in df.columns:
        df["radam_forest_ha"] = num(df, "radam_FLORESTA_ha")
    if "radam_cerrado_ha" not in df.columns:
        df["radam_cerrado_ha"] = num(df, "radam_CERRADO_ha")
    if "radam_total_ha" not in df.columns:
        df["radam_total_ha"] = num(df, "radam_forest_ha") + num(df, "radam_cerrado_ha")
    if "app_req_ha" not in df.columns:
        df["app_req_ha"] = num(df, "app")

    df["mun_geocodigo"] = derive_municipality_code(df)
    df["car_valid"] = boolish(df, "car_valid", default=True)
    df["calc_gross_deficit_total_ha"] = num(df, "rl_gross_deficit_ha") + num(df, "app_gross_deficit_ha")
    df["calc_deficit_total_ha"] = num(df, "rl_adj_deficit_ha") + num(df, "app_restore_ha")
    return df


def load_all_sources() -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    audit_rows = []
    wanted = list(dict.fromkeys(ID_COLS + METRIC_COLS))

    for source in ["simcar_validado", "simcar_digital", "simcar_proxy"]:
        path = INPUTS[source]
        if not path.exists():
            raise FileNotFoundError(f"Missing input for {source}: {path}")
        df = normalize_source(read_existing_columns(path, wanted), source, path)
        # Validated and digital SIMCAR expose the official AREA_CONSOLIDADA
        # layer, historically retained here under the legacy name
        # cons_area_2000. Export it explicitly as the semantically correct
        # 2008 field as well, without changing the legacy 2000-rule scenario.
        if source in {"simcar_validado", "simcar_digital"} and "cons_area_2008" not in df.columns:
            df["cons_area_2008"] = num(df, "cons_area_2000")
        if source == "simcar_digital":
            digital_cols = [
                "app", "app_fnl_auas", "cons_area_2000", "arl_declared_ha",
                "auas_post2008", "avn_declared_ha", "area_declividade",
                "area_inundada", "area_topo_morro", "area_umida",
                "borda_chapada", "interesse_social", "lagoa_natural",
                "manguezal", "nascente", "reservatorio_artificial",
                "restinga", "rio_10_a_50",
            ]
            present = [c for c in digital_cols if c in df.columns]
            if present:
                has_digital_data = df[present].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1) > 0
                df = df.loc[has_digital_data].copy()
        elif source == "simcar_validado":
            validado_cols = [
                "app", "appd_declared_ha", "apprl_declared_ha",
                "arl_declared_ha", "au_declared_ha", "auas_post2008",
                "avn_declared_ha", "nascente", "arld_declared_ha",
                "cons_area_2000", "utilidade_publica",
            ]
            present = [c for c in validado_cols if c in df.columns]
            if present:
                has_validado_data = df[present].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1) > 0
                df = df.loc[has_validado_data].copy()
        frames.append(df)
        audit_rows.append({
            "input_file_type": source,
            "input_priority": SOURCE_PRIORITY[source],
            "input_file": str(path),
            "raw_rows": len(df),
            "unique_priority_keys": df["priority_key"].nunique(dropna=True),
        })

    raw = pd.concat(frames, ignore_index=True, sort=False)
    raw = raw.sort_values(["input_priority", "priority_key"], kind="mergesort")
    consolidated = raw.drop_duplicates(subset=["priority_key"], keep="first").reset_index(drop=True)

    selected_counts = ordered_input_counts(consolidated["input_file_type"]).to_dict()
    for row in audit_rows:
        row["selected_rows_after_priority"] = int(selected_counts.get(row["input_file_type"], 0))
        row["removed_by_higher_priority"] = int(row["raw_rows"] - row["selected_rows_after_priority"])

    return consolidated, pd.DataFrame(audit_rows)


def grouped_summary(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    work = apply_source_order(df)
    for col in CANONICAL_NUMERIC:
        work[col] = num(work, col)
    out = (
        work.groupby(group_cols, dropna=False, observed=False)
        .agg(
            n_properties=("priority_key", "size"),
            n_valid_car=("car_valid", "sum"),
            total_area_ha=("area_ha_car", "sum"),
            radam_total_ha=("radam_total_ha", "sum"),
            rl_required_ha=("rl_req_total_ha", "sum"),
            rl_existing_ha=("rl_exist_total_ha", "sum"),
            rl_gross_deficit_ha=("rl_gross_deficit_ha", "sum"),
            rl_adjusted_deficit_ha=("rl_adj_deficit_ha", "sum"),
            rl_surplus_ha=("rl_surplus_total_ha", "sum"),
            rl_restore_ha=("rl_restore_ha", "sum"),
            rl_compensate_ha=("rl_compensate_ha", "sum"),
            app_required_ha=("app_req_ha", "sum"),
            app_preserved_ha=("app_preserved_ha", "sum"),
            app_gross_deficit_ha=("app_gross_deficit_ha", "sum"),
            app_restore_ha=("app_restore_ha", "sum"),
            total_deficit_ha=("calc_deficit_total_ha", "sum"),
        )
        .reset_index()
    )
    sort_cols = [c for c in ["input_file_type", "size_class"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, kind="stable").reset_index(drop=True)
    return out


def make_final_tables(df: pd.DataFrame, audit: pd.DataFrame) -> dict[str, pd.DataFrame]:
    active = df[df["car_valid"] == True].copy()
    tables = {
        "input_priority_audit": audit,
        "fc_summary_by_source": grouped_summary(df, ["input_file_type"]),
        "fc_summary_active_by_source": grouped_summary(active, ["input_file_type"]),
        "fc_summary_size_source": grouped_summary(df, ["input_file_type", "size_class"]),
        "fc_summary_size_active": grouped_summary(active, ["input_file_type", "size_class"]),
        "fc_summary_overall": grouped_summary(df.assign(group="all_sources"), ["group"]),
    }
    return tables


def write_outputs(df: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> dict[str, Path]:
    df = df.sort_values(["input_priority", "priority_key"], kind="stable").reset_index(drop=True)
    today = paths.RUN_DATE
    parquet_path = OUT_DIR / f"forest_code_mt_priority_consolidated_{today}.parquet"
    excel_path = OUT_DIR / f"forest_code_mt_priority_tables_{today}.xlsx"
    export_csv = os.environ.get("FCM_EXPORT_CONSOLIDATED_CSV", "").lower() in {"1", "true", "yes"}
    csv_path = OUT_DIR / f"forest_code_mt_priority_consolidated_{today}.csv" if export_csv else None

    df.to_parquet(parquet_path, index=False)
    if csv_path is not None:
        df.to_csv(csv_path, index=False)

    raw_cols = [
        "input_file_type", "input_priority", "property_code", "property_join_key",
        "NOMESPROPR", "NOMEPROPRI", "NUMEROESTA", "PROTOCOLO", "SITUACAO",
        "MUNICIPIO_", "mun_geocodigo", "car_valid", "size_class", "area_ha_car",
        "radam_total_ha", "rl_req_total_ha", "rl_exist_total_ha",
        "rl_adj_deficit_ha", "rl_restore_ha", "rl_compensate_ha", "app_req_ha",
        "app_preserved_ha", "app_gross_deficit_ha", "app_restore_ha",
        "calc_gross_deficit_total_ha",
        "calc_deficit_total_ha",
    ]
    raw_cols = [c for c in raw_cols if c in df.columns]

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        pd.DataFrame({
            "item": [
                "description", "priority_order", "full_consolidated_parquet",
                "full_consolidated_csv", "rows_in_excel_raw_sheet",
            ],
            "value": [
                "Forest Code final tables consolidated by CAR priority.",
                "1 SIMCAR validated; 2 SIMCAR digital; 3 SIMCAR proxy",
                str(parquet_path), str(csv_path) if csv_path is not None else "not exported by default", len(df),
            ],
        }).to_excel(writer, sheet_name="README", index=False)
        for name, table in tables.items():
            table.to_excel(writer, sheet_name=name[:31], index=False)
        df[raw_cols].to_excel(writer, sheet_name="fc_consolidated_raw", index=False)

    outputs = {"parquet": parquet_path, "excel": excel_path}
    if csv_path is not None:
        outputs["csv"] = csv_path
    return outputs


def main() -> dict[str, Path]:
    df, audit = load_all_sources()
    tables = make_final_tables(df, audit)
    outputs = write_outputs(df, tables)
    print("Forest Code consolidated rows:", len(df))
    print("Rows by input:")
    print(ordered_input_counts(df["input_file_type"]).to_string())
    for key, path in outputs.items():
        print(f"{key}: {path}")
    return outputs


if __name__ == "__main__":
    main()

