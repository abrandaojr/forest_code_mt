from __future__ import annotations

import os
import json
from pathlib import Path


ROOT = Path(os.environ.get("FCM_ROOT", Path(__file__).resolve().parents[1]))
CONFIG_PATH = ROOT / "config.json"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


CONFIG = _load_config()


def rel_path(key: str, default: str) -> Path:
    return ROOT / CONFIG.get("paths", {}).get(key, default)


def input_path(key: str, default: str) -> Path:
    return ROOT / CONFIG.get("inputs", {}).get(key, default)


CODE = rel_path("code", "code")
DOCS = rel_path("doc", "doc")
QC = rel_path("qa", "qa")
DATA = rel_path("data", "data")
RAW = Path(os.environ.get("FCM_RAW_DIR", rel_path("raw", "data/raw")))
PRE = Path(os.environ.get("FCM_PREPROCESSED_DIR", rel_path("pre", "data/pre")))
PROC = Path(os.environ.get("FCM_PROCESSED_DIR", rel_path("proc", "data/proc")))
OUT = rel_path("out", "out")
TABLES = Path(os.environ.get("FCM_TABLES_DIR", rel_path("table", "out/table")))
FIGURES = Path(os.environ.get("FCM_FIGURES_DIR", rel_path("fig", "out/fig")))
REPORTS = Path(os.environ.get("FCM_REPORTS_DIR", rel_path("report", "out/report")))
QGIS = Path(os.environ.get("FCM_QGIS_DIR", rel_path("qgis", "out/qgis")))

GTA_CSV = input_path("gta_csv", "data/raw/gta/erich_car_gta.csv")
MUNICIPALITIES = input_path("municipalities", "data/raw/reference_maps/lml_municipio_a.parquet")
STATES = input_path("states", "data/raw/reference_maps/lml_unidade_federacao_a.parquet")
CAR_VALIDATED = input_path("car_validated", "data/raw/simcar_validado/CAR_ATP.parquet")
CAR_DIGITAL_MASTER = input_path("car_digital_master", "data/proc/simcar_digital/simcar_digital_march2026_geo_master.parquet")
CAR_PROXY_MASTER = input_path("car_proxy_master", "data/proc/simcar_proxy/simcar_p_march2026_geo_master.parquet")
CAR_PRE = CONFIG.get("car_pre", {"simcar_validado": "car_validated", "simcar_digital": "car_digital", "simcar_proxy": "car_proxy"})
RUN_DATE = str(CONFIG.get("run", {}).get("date", "20260818"))


def workers() -> int:
    cpu = os.cpu_count() or 1
    fraction = float(CONFIG.get("run", {}).get("cpu_fraction", 0.8))
    default = max(1, int(cpu * fraction))
    value = os.environ.get("FCM_WORKERS")
    if value:
        return max(1, min(cpu, int(value)))
    return default


def set_env() -> None:
    n = str(workers())
    os.environ["FCM_ROOT"] = str(ROOT)
    os.environ["FCM_RAW_DIR"] = str(RAW)
    os.environ["FCM_DATA_DIR"] = str(RAW)
    os.environ["FCM_PREPROCESSED_DIR"] = str(PRE)
    os.environ["FCM_PROCESSED_DIR"] = str(PROC)
    os.environ["FCM_OUTPUT_DIR"] = str(OUT)
    os.environ["FCM_FINAL_OUT_DIR"] = str(TABLES)
    os.environ["FCM_TABLES_DIR"] = str(TABLES)
    os.environ["FCM_FIGURES_DIR"] = str(FIGURES)
    os.environ["FCM_REPORTS_DIR"] = str(REPORTS)
    os.environ["FCM_QGIS_DIR"] = str(QGIS)
    os.environ["MAKE_A_MAP_SRC"] = str(CODE)
    os.environ["FCM_WORKERS"] = n
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ.setdefault("OMP_NUM_THREADS", n)
    os.environ.setdefault("MKL_NUM_THREADS", n)
    os.environ.setdefault("OPENBLAS_NUM_THREADS", n)
    os.environ.setdefault("NUMEXPR_NUM_THREADS", n)
    os.environ.setdefault("GDAL_NUM_THREADS", n)

