"""Build mutually exclusive APP classes for every prioritized MT property."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"
TABLE = ROOT / "out/table/forest_code_mt_priority_consolidated_20261007.parquet"
OUT = ROOT / "data/pre/statewide_app_partition_20261007.parquet"
QA = ROOT / "qa/statewide_app_partition_20261007.json"

SOURCES = {
    "simcar_validado": (RAW / "simcar_validado/CAR_APP_x_car_atp.parquet", RAW / "simcar_validado/CAR_AUAS_x_car_atp.parquet", "prop_id_unique"),
    "simcar_digital": (RAW / "simcar_digital/SIMCAR_D_APP_x_car_atp.parquet", RAW / "simcar_digital/SIMCAR_D_AUAS_x_car_atp.parquet", "car_OBJECTID"),
    "simcar_proxy": (RAW / "simcar_proxy/SIMCAR_P_app_x_car_atp_fnl.parquet", RAW / "simcar_proxy/SIMCAR_P_auas_post2008_x_car_atp.parquet", "car_join"),
}


def load_selected(path: Path, key: str, selected: set) -> gpd.GeoDataFrame:
    schema = pq.ParquetFile(path).schema_arrow.names
    cols = [c for c in [key, "geometry"] if c in schema]
    g = gpd.read_parquet(path, columns=cols)
    if key == "car_OBJECTID":
        g[key] = pd.to_numeric(g[key], errors="coerce").astype("Int64")
    else:
        g[key] = g[key].astype("string")
    g = g[g[key].isin(selected) & g.geometry.notna()].copy()
    g = g[~g.geometry.is_empty]
    return g[[key, "geometry"]]


def dissolve_map(g: gpd.GeoDataFrame, key: str) -> dict:
    if g.empty:
        return {}
    return g.groupby(key, observed=True).geometry.apply(lambda s: shapely.union_all(s.array)).to_dict()


def intersect_native_chunk(args):
    start, stop, app_chunk, post_chunk, native_tree, native_tiles = args
    left, right = native_tree.query(app_chunk, predicate="intersects")
    parts = shapely.intersection(app_chunk[left], native_tiles.take(right))
    parts = shapely.difference(parts, post_chunk[left])
    areas = np.bincount(left, weights=shapely.area(parts) / 10000, minlength=len(app_chunk))
    return start, stop, areas


def main() -> None:
    priority = pd.read_parquet(TABLE, columns=["priority_key", "input_file_type", "car_join", "prop_id_unique"])
    vegetation = gpd.read_file(RAW / "simcar_proxy/input_prodes_native_vegetation_2024_plus_sv.shp")
    vegetation = vegetation[vegetation["layer"].isin(["input_prodes_native_vegetation_2024_TILED", "input_secondary_forest_dissolved"]) & vegetation.geometry.notna()].copy()
    vegetation = vegetation[~vegetation.geometry.is_empty]
    print("vegetation: dissolving non-overlapping tile masks", flush=True)
    groups = [s.array for _, s in vegetation.groupby("tile_id", observed=True).geometry]
    with ThreadPoolExecutor(max_workers=8) as pool:
        native_tiles = np.asarray(list(pool.map(shapely.union_all, groups)), dtype=object)
    native_tree = STRtree(native_tiles)
    del vegetation

    all_rows = []
    source_stats = {}
    for source, (app_path, auas_path, key) in SOURCES.items():
        print(source, "selecting source rows", flush=True)
        subset = priority[priority["input_file_type"].eq(source)].copy()
        if key == "car_OBJECTID":
            subset[key] = pd.to_numeric(subset["car_join"].str.extract(r"(\d+)$")[0], errors="coerce").astype("Int64")
        else:
            subset[key] = subset[key].astype("string")
        selected = set(subset[key].dropna().tolist())
        print(source, "loading and dissolving APP", flush=True)
        app_map = dissolve_map(load_selected(app_path, key, selected), key)
        print(source, "loading and dissolving AUAS", flush=True)
        auas_map = dissolve_map(load_selected(auas_path, key, selected), key)

        print(source, "intersecting vegetation and temporal classes", flush=True)
        identifiers = np.asarray(list(app_map.keys()), dtype=object)
        app_geoms = np.asarray([shapely.make_valid(app_map[k]) for k in identifiers], dtype=object)
        empty = shapely.GeometryCollection()
        auas_geoms = np.asarray([auas_map.get(k, empty) for k in identifiers], dtype=object)
        post_geoms = shapely.intersection(app_geoms, auas_geoms)
        app_area = shapely.area(app_geoms) / 10000
        post_area = shapely.area(post_geoms) / 10000

        # Tile masks remove within-tile overlaps and reduce each APP query to a
        # few large non-overlapping candidates rather than thousands of source
        # fragments.
        chunk_size = 250
        jobs = [
            (start, min(start + chunk_size, len(app_geoms)),
             app_geoms[start:start + chunk_size], post_geoms[start:start + chunk_size],
             native_tree, native_tiles)
            for start in range(0, len(app_geoms), chunk_size)
        ]
        native_area = np.zeros(len(app_geoms), dtype=float)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for start, stop, areas in pool.map(intersect_native_chunk, jobs):
                native_area[start:stop] = areas
        available = np.maximum(app_area - post_area, 0)
        native_overlap_excess = np.maximum(native_area - available, 0)
        native_area = np.minimum(native_area, available)
        pre_area = np.maximum(app_area - post_area - native_area, 0)
        closure = native_area + pre_area + post_area - app_area
        frame = pd.DataFrame({
            key: identifiers,
            "app_partition_total_ha": app_area,
            "app_partition_native_ha": native_area,
            "app_partition_pre2008_ha": pre_area,
            "app_partition_post2008_ha": post_area,
            "app_partition_closure_error_ha": closure,
            "app_native_overlap_excess_ha": native_overlap_excess,
        })
        frame = subset[["priority_key", key]].merge(frame, on=key, how="left").drop(columns=key)
        for c in frame.columns[1:]: frame[c] = pd.to_numeric(frame[c], errors="coerce").fillna(0.0)
        frame["input_file_type"] = source
        all_rows.append(frame)
        source_stats[source] = {
            "properties": len(subset), "with_app_geometry": len(app_map),
            "max_abs_closure_error_ha": float(frame.app_partition_closure_error_ha.abs().max()),
            "properties_with_native_overlap_excess": int((frame.app_native_overlap_excess_ha > 0.01).sum()),
        }
        print(source, source_stats[source], flush=True)

    result = pd.concat(all_rows, ignore_index=True)
    assert result["priority_key"].is_unique
    assert len(result) == len(priority)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(OUT, index=False)
    QA.parent.mkdir(parents=True, exist_ok=True)
    QA.write_text(json.dumps({"rows": len(result), "sources": source_stats, "max_abs_closure_error_ha": float(result.app_partition_closure_error_ha.abs().max())}, indent=2), encoding="utf-8")
    print(OUT, flush=True)


if __name__ == "__main__":
    main()
