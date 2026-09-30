"""Render the two worked-example CAR polygons over Esri World Imagery."""

from pathlib import Path
from io import BytesIO
import math

import geopandas as gpd
import matplotlib.pyplot as plt
import pyarrow.parquet as pq
import requests
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "deliverables" / "04_presentation" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

EXAMPLES = [
    {
        "label": "large_property",
        "path": ROOT / "data" / "raw" / "simcar_requerido" / "CAR_ATP.parquet",
        "field": "CODIGO_CAR",
        "key": "MT-5107875-FCDC7412E5B04C10A7B5B8FA8CE4B049",
        "color": "#8BC34A",
    },
    {
        "label": "small_property",
        "path": ROOT / "data" / "raw" / "simcar_validado" / "CAR_ATP.parquet",
        "field": "CAR_FEDERA",
        "key": "MT-5103437-3035138E282C4E6686B61959CF506B0D",
        "color": "#FFB23E",
    },
]


def load_one(spec):
    table = pq.read_table(
        spec["path"],
        columns=[spec["field"], "geometry"],
        filters=[(spec["field"], "=", spec["key"])],
    )
    frame = gpd.GeoDataFrame.from_arrow(table)
    if frame.empty:
        raise RuntimeError(f"Property not found: {spec['key']}")
    frame = frame.dissolve(by=spec["field"]).reset_index()
    if frame.crs is None:
        raise RuntimeError(f"Missing CRS: {spec['path']}")
    return frame


WEB_HALF = 20037508.342789244
WORLD = 2 * WEB_HALF


def tile_xy(x, y, zoom):
    n = 2 ** zoom
    return int((x + WEB_HALF) / WORLD * n), int((WEB_HALF - y) / WORLD * n)


def tile_bounds(x, y, zoom):
    n = 2 ** zoom
    return (
        x / n * WORLD - WEB_HALF,
        WEB_HALF - (y + 1) / n * WORLD,
        (x + 1) / n * WORLD - WEB_HALF,
        WEB_HALF - y / n * WORLD,
    )


def esri_mosaic(bounds, target_px=1450):
    minx, miny, maxx, maxy = bounds
    span = max(maxx - minx, maxy - miny)
    zoom = max(4, min(18, int(math.log2(WORLD * target_px / max(span * 256, 1)))))
    x0, y1 = tile_xy(minx, miny, zoom)
    x1, y0 = tile_xy(maxx, maxy, zoom)
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1))
    canvas = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    session = requests.Session()
    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{ty}/{tx}"
            response = session.get(url, timeout=30)
            response.raise_for_status()
            canvas.paste(Image.open(BytesIO(response.content)).convert("RGB"), ((tx - x0) * 256, (ty - y0) * 256))
    left, bottom, _, _ = tile_bounds(x0, y1, zoom)
    _, _, right, top = tile_bounds(x1, y0, zoom)
    return canvas, (left, right, bottom, top)


def render(spec):
    prop = load_one(spec).to_crs(3857)
    minx, miny, maxx, maxy = prop.total_bounds
    span = max(maxx - minx, maxy - miny)
    pad = max(span * 0.28, 900)

    fig, ax = plt.subplots(figsize=(14, 8.4), dpi=180)
    ax.set_xlim(minx - pad, maxx + pad)
    ax.set_ylim(miny - pad, maxy + pad)
    mosaic, extent = esri_mosaic((minx - pad, miny - pad, maxx + pad, maxy + pad))
    ax.imshow(mosaic, extent=extent, origin="upper")
    prop.plot(ax=ax, facecolor=spec["color"] + "22", edgecolor="white", linewidth=5)
    prop.plot(ax=ax, facecolor="none", edgecolor=spec["color"], linewidth=2.5)

    # Scale bar sized to the property extent.
    scale = 1000 if span < 12000 else 5000
    x0 = minx - pad * 0.75
    y0 = miny - pad * 0.72
    ax.plot([x0, x0 + scale], [y0, y0], color="white", linewidth=6, solid_capstyle="butt")
    ax.plot([x0, x0 + scale], [y0, y0], color="#17312B", linewidth=2, solid_capstyle="butt")
    ax.text(x0 + scale / 2, y0 + pad * 0.07, f"{scale/1000:g} km", ha="center", va="bottom", color="white", fontsize=10, weight="bold")

    # North arrow.
    ax.annotate("N", xy=(0.94, 0.90), xytext=(0.94, 0.78), xycoords="axes fraction",
                color="white", fontsize=13, weight="bold", ha="center",
                arrowprops=dict(facecolor="white", edgecolor="#17312B", width=3, headwidth=11))
    ax.text(0.995, 0.012, "Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5, color="white",
            bbox=dict(facecolor="black", alpha=0.48, edgecolor="none", pad=2))
    ax.set_axis_off()
    fig.tight_layout(pad=0)
    target = OUT / f"{spec['label']}_satellite_map.png"
    fig.savefig(target, dpi=180, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    return target


if __name__ == "__main__":
    for example in EXAMPLES:
        print(render(example))
