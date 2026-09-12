from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import _00_paths as paths

paths.set_env()
ROOT = paths.ROOT
QC_DIR = paths.QC
QC_DIR.mkdir(parents=True, exist_ok=True)

TRACKED_SUFFIXES = {".parquet", ".gpkg", ".shp", ".tif", ".tiff"}

SOURCE_URLS = {
    "geoportal": "https://geoportal.sema.mt.gov.br/",
    "prodes": "https://terrabrasilis.dpi.inpe.br/en/download-files/",
}


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("/", "\\")


def infer_source(path: Path) -> tuple[str, str, str, str]:
    s = rel(path).lower()
    name = path.name.lower()

    if "gta" in s:
        return ("GTA cattle movement table", "raw tabular input", "csv", "")
    if "reference_maps" in s or "bc250" in s or "lml_municipio" in s or "lml_unidade_federacao" in s:
        return ("IBGE BC250 reference boundaries", "raw converted reference map", "shapefile/geodatabase converted to GeoParquet", "")
    if "prodes" in s or "native_veg" in s or "consolidated" in s or "cons_area" in s or "auas_post2008" in s:
        return ("INPE PRODES / TerraBrasilis native vegetation derivatives", "raw converted or derived land-cover layer", "PRODES vector/TIFF processed to GeoParquet or raster derivative", SOURCE_URLS["prodes"])
    if "secondary_forest" in s or "secondary_vegetation" in s:
        return ("INPE secondary vegetation", "raw converted or scenario input", "source vector converted to GeoParquet", SOURCE_URLS["prodes"])
    if "sfb" in s or "hidro" in s or "hydro" in s or "water" in s:
        return ("Brazilian Forest Service / SFB hydrography", "raw converted hydrography or APP model input", "SFB shapefile/geodatabase converted to GeoParquet", "")
    if "radam" in s or "vegetacao_radam" in s or "vegetation_radam" in s:
        return ("RADAMBrasil / SEMA vegetation typology", "raw converted vegetation typology or intersect", "RADAM/Geoportal shapefile converted to GeoParquet", SOURCE_URLS["geoportal"])
    if "simcar_validado" in s or "\\car_atp.parquet" in s and "validado" in s:
        return ("Geoportal/SEMA-MT SIMCAR validado", "raw converted or source-specific intersect", "Geoportal shapefile/zip converted to GeoParquet", SOURCE_URLS["geoportal"])
    if "simcar_digital" in s or name.startswith("simcar_d_") or "\\simcar\\" in s and "digital" in s:
        return ("Geoportal/SEMA-MT CAR Digital", "raw converted or source-specific intersect", "Geoportal shapefile/zip converted to GeoParquet", SOURCE_URLS["geoportal"])
    if "simcar_proxy" in s or "simcar_p_" in name or "simcar_p_" in s or "simcar_requerido" in s or "mvw_requerimento" in s:
        return ("Geoportal/SEMA-MT SIMCAR requerido/proxy", "raw converted or proxy-derived layer", "Geoportal shapefile/zip converted to GeoParquet", SOURCE_URLS["geoportal"])
    if "\\intersects\\" in s:
        return ("Mixed geospatial source", "precomputed spatial intersection", "converted GeoParquet inputs intersected with CAR", "")
    if "\\data\\proc\\" in s:
        return ("Geoportal/SEMA-MT property geometry master", "raw converted property geometry master", "Geoportal shapefile/zip converted to GeoParquet", SOURCE_URLS["geoportal"])
    return ("Unclassified package data", "unknown or auxiliary", "unknown", "")


def infer_stage(path: Path) -> str:
    s = rel(path).lower()
    if s.startswith("data\\raw"):
        return "data/raw"
    if s.startswith("data\\pre"):
        return "data/pre"
    if s.startswith("data\\proc"):
        return "data/proc"
    if s.startswith("out"):
        return "out"
    return "other"


def infer_portability(path: Path) -> str:
    s = rel(path).lower()
    if s.startswith("data\\raw"):
        return "direct package input"
    if "car_proxy" in s or "car_digital" in s or "car_validated" in s or "\\data\\proc\\" in s:
        return "portable precomputed input for final pipeline"
    if path.suffix.lower() in {".tif", ".tiff"}:
        return "raster derivative retained outside raw folder"
    return "supporting/intermediate package data"


def iter_records() -> list[dict[str, str | int | float]]:
    records = []
    for base in ["data/raw", "data/pre", "data/proc"]:
        root = ROOT / base
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TRACKED_SUFFIXES:
                continue
            source, role, original, url = infer_source(path)
            records.append(
                {
                    "relative_path": rel(path),
                    "stage_folder": infer_stage(path),
                    "extension": path.suffix.lower(),
                    "size_mb": round(path.stat().st_size / 1024 / 1024, 4),
                    "inferred_source": source,
                    "source_url": url,
                    "lineage_role": role,
                    "original_format_assumption": original,
                    "pipeline_portability_role": infer_portability(path),
                }
            )
    return sorted(records, key=lambda r: str(r["relative_path"]).lower())


def write_manifest(records: list[dict[str, str | int | float]]) -> tuple[Path, Path]:
    today = paths.RUN_DATE
    csv_path = QC_DIR / f"geoparquet_raw_provenance_manifest_{today}.csv"
    json_path = QC_DIR / f"geoparquet_raw_provenance_manifest_{today}.json"
    if records:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)
    json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    return csv_path, json_path


def write_summary(records: list[dict[str, str | int | float]]) -> Path:
    today = paths.RUN_DATE
    summary_path = QC_DIR / f"geoparquet_raw_provenance_summary_{today}.md"
    by_source: dict[str, Counter] = defaultdict(Counter)
    by_stage: Counter = Counter()
    for r in records:
        source = str(r["inferred_source"])
        by_source[source]["files"] += 1
        by_source[source]["size_mb"] += float(r["size_mb"])
        by_stage[str(r["stage_folder"])] += 1

    lines = [
        f"# GeoParquet raw provenance summary - {today}",
        "",
        "This manifest treats converted GeoParquets as raw-converted data when they preserve source-layer content or serve as the direct geospatial inputs for final Forest Code calculations.",
        "",
        "## Files by package stage",
        "",
        "| stage | files |",
        "|---|---:|",
    ]
    for stage, count in sorted(by_stage.items()):
        lines.append(f"| {stage} | {count:,} |")

    lines.extend(["", "## Files by inferred source", "", "| inferred source | files | size MB |", "|---|---:|---:|"])
    for source, counter in sorted(by_source.items()):
        lines.append(f"| {source} | {int(counter['files']):,} | {counter['size_mb']:,.1f} |")

    lines.extend(
        [
            "",
            "## Important interpretation",
            "",
            "- `data/raw` contains minimal raw and raw-converted inputs.",
            "- The final pipeline consumes precomputed property-intersect GeoParquets for the spatially heavy steps.",
            "- `data/pre` contains current summary outputs.",
            "- `data/proc` contains geometry masters.",
            "- Converted GeoParquets are the retained raw inputs for this portable package.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def main() -> dict[str, Path]:
    records = iter_records()
    csv_path, json_path = write_manifest(records)
    summary_path = write_summary(records)
    print(f"Provenance records: {len(records):,}")
    print(f"csv: {csv_path}")
    print(f"json: {json_path}")
    print(f"summary: {summary_path}")
    return {"csv": csv_path, "json": json_path, "summary": summary_path}


if __name__ == "__main__":
    main()

