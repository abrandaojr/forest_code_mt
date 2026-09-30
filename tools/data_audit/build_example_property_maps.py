"""Render the two worked-example CAR polygons over Esri World Imagery."""

from pathlib import Path
from io import BytesIO
import math

import geopandas as gpd
import matplotlib.pyplot as plt
import pyarrow.parquet as pq
import requests
from PIL import Image
import pandas as pd


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
        "join": "car_115587",
        "objectid": 115587,
        "source": "digital",
    },
    {
        "label": "small_property",
        "path": ROOT / "data" / "raw" / "simcar_validado" / "CAR_ATP.parquet",
        "field": "CAR_FEDERA",
        "key": "MT-5103437-3035138E282C4E6686B61959CF506B0D",
        "color": "#FFB23E",
        "join": "MT37754/2020_|_MT-5103437-3035138E282C4E6686B61959CF506B0D_|_24389",
        "proxy_join": "car_145560",
        "cons2000_join": "car_172072",
        "source": "validated",
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


def read_geometry(path, filters=None):
    """Read only geometry and useful labels from an intersect GeoParquet."""
    path = Path(path)
    if not path.exists():
        return None
    schema = pq.ParquetFile(path).schema_arrow.names
    wanted = [c for c in [
        "geometry", "car_join", "prop_id_unique", "car_OBJECTID",
        "FITOECOLOG", "lyr_FITOECOLOG", "area_ha", "Shape_Area",
    ] if c in schema]
    try:
        return gpd.read_parquet(path, columns=wanted, filters=filters)
    except Exception:
        table = pq.read_table(path, columns=wanted, filters=filters)
    try:
        return gpd.GeoDataFrame.from_arrow(table)
    except Exception:
        table = pq.read_table(path, columns=wanted)
        frame = table.to_pandas()
        for col, op, value in filters or []:
            if op == "=":
                frame = frame[frame[col] == value]
        if frame.empty:
            return gpd.GeoDataFrame(frame, geometry="geometry")
        if "geometry" in frame.columns:
            import shapely
            frame["geometry"] = shapely.from_wkb(frame["geometry"].to_numpy())
        return gpd.GeoDataFrame(frame, geometry="geometry", crs=ESRI_102033)


def clip_to_property(layer, prop):
    if layer is None or layer.empty:
        return None
    if layer.crs != prop.crs:
        layer = layer.to_crs(prop.crs)
    clipped = gpd.clip(layer, prop)
    return None if clipped.empty else clipped


def layer_area(layer):
    if layer is None or layer.empty:
        return 0.0
    metric = layer.to_crs(ESRI_102033)
    return float(metric.geometry.area.sum() / 10000)


ESRI_102033 = "+proj=aea +lat_0=-32 +lon_0=-60 +lat_1=-5 +lat_2=-42 +x_0=0 +y_0=0 +datum=SAD69 +units=m +no_defs"


def example_layers(spec):
    prop = load_one(spec)
    root = ROOT / "data" / "raw"
    proxy = root / "simcar_proxy"
    if spec["source"] == "digital":
        oid = spec["objectid"]
        f = [("car_OBJECTID", "=", oid)]
        source = root / "simcar_digital"
        layers = {
            "radam": read_geometry(proxy / "SIMCAR_P_vegetacao_radambrasil_x_car_atp.parquet", [("car_join", "=", spec["join"])]),
            "native": read_geometry(proxy / "SIMCAR_P_vegetacao_radambrasil_x_car_atp_nveg24.parquet", [("car_join", "=", spec["join"])]),
            "cons2000": read_geometry(proxy / "SIMCAR_P_cons_area_2000_net_max_x_car_atp.parquet", [("car_join", "=", spec["join"])]),
            "cons2008": read_geometry(source / "SIMCAR_D_AREA_CONSOLIDADA_x_car_atp.parquet", f),
            "auas": read_geometry(source / "SIMCAR_D_AUAS_x_car_atp.parquet", f),
            "app": read_geometry(source / "SIMCAR_D_APP_x_car_atp.parquet", f),
            "avn": read_geometry(source / "SIMCAR_D_AVN_x_car_atp.parquet", f),
            "appd": read_geometry(source / "SIMCAR_D_APPD_4A10MF_AC_x_car_atp.parquet", f),
            "app_auas": read_geometry(source / "SIMCAR_D_APPD_AUAS_x_car_atp.parquet", f),
        }
    else:
        f = [("prop_id_unique", "=", spec["join"])]
        source = root / "simcar_validado"
        layers = {
            "radam": read_geometry(proxy / "SIMCAR_P_vegetacao_radambrasil_x_car_atp.parquet", [("car_join", "=", spec["proxy_join"])]),
            "cons2000": read_geometry(proxy / "SIMCAR_P_cons_area_2000_net_max_x_car_atp.parquet", [("car_join", "=", spec["cons2000_join"])]),
            "cons2008": read_geometry(source / "SIMCAR_CAR_AREA_CONSOLIDADA_x_car_atp.parquet", f),
            "auas": read_geometry(source / "CAR_AUAS_x_car_atp.parquet", f),
            "app": read_geometry(source / "CAR_APP_x_car_atp.parquet", f),
            "avn": read_geometry(source / "CAR_AVN_x_car_atp.parquet", f),
            "appd": read_geometry(source / "CAR_APPD_x_car_atp.parquet", f),
            "app_auas": None,
        }
        # The authoritative current-vegetation and secondary-vegetation values
        # are spatial intersections of this source vector with the property.
        src = gpd.read_file(proxy / "input_prodes_native_vegetation_2024_plus_sv.shp", bbox=tuple(prop.total_bounds))
        layers["native"] = src[src["layer"].astype(str).eq("input_prodes_native_vegetation_2024_TILED")].copy()
    src = gpd.read_file(proxy / "input_prodes_native_vegetation_2024_plus_sv.shp", bbox=tuple(prop.total_bounds))
    layers["secondary"] = src[src["layer"].astype(str).eq("input_secondary_forest_dissolved")].copy()
    return prop, {k: clip_to_property(v, prop) for k, v in layers.items()}


def draw_layer_panel(ax, prop, layer, title, reported, color, mosaic, extent, categorical=False):
    ax.imshow(mosaic, extent=extent, origin="upper")
    if layer is not None and not layer.empty:
        layer = layer.to_crs(3857)
        if categorical:
            field = "FITOECOLOG" if "FITOECOLOG" in layer.columns else "lyr_FITOECOLOG"
            values = layer[field].astype(str).str.upper() if field in layer.columns else pd.Series("OTHER", index=layer.index)
            for label, shade in [("FLORESTA", "#1E6B52"), ("CERRADO", "#D49A45")]:
                part = layer[values.eq(label)]
                if not part.empty:
                    part.plot(ax=ax, facecolor=shade, edgecolor="white", linewidth=1.2, alpha=0.62)
        else:
            layer.plot(ax=ax, facecolor=color, edgecolor="white", linewidth=1.2, alpha=0.62)
    prop.to_crs(3857).plot(ax=ax, facecolor="none", edgecolor="#FFFFFF", linewidth=2.8)
    prop.to_crs(3857).plot(ax=ax, facecolor="none", edgecolor="#17312B", linewidth=1.1)
    ax.set_title(f"{title}\n{reported}", loc="left", fontsize=12, weight="bold", color="#17312B", pad=7)
    if layer is None or layer.empty:
        ax.text(.5, .5, "NO INTERSECTING FEATURE", transform=ax.transAxes, ha="center", va="center",
                fontsize=10, weight="bold", color="#B95B4C", bbox=dict(facecolor="white", alpha=.88, edgecolor="none", pad=5))
    ax.set_axis_off()


def render_layer_atlases(spec):
    prop, layers = example_layers(spec)
    prop3857 = prop.to_crs(3857)
    minx, miny, maxx, maxy = prop3857.total_bounds
    span = max(maxx - minx, maxy - miny)
    pad = max(span * .18, 500)
    mosaic, extent = esri_mosaic((minx-pad, miny-pad, maxx+pad, maxy+pad), target_px=900)
    reported = {
        "large_property": {"radam":"Forest 169.21 ha | Cerrado 430.71 ha", "native":"Current native vegetation 118.13 ha", "secondary":"Secondary vegetation 79.11 ha", "cons2000":"273.13 ha", "cons2008":"0.00 ha", "auas":"0.00004 ha", "app":"APP requirement 8.65 ha", "avn":"Declared native vegetation 115.46 ha", "appd":"0.00 ha", "app_auas":"0.00 ha"},
        "small_property": {"radam":"Forest 108.66 ha | Cerrado 80.90 ha", "native":"Current native vegetation 61.34 ha", "secondary":"Secondary vegetation 48.40 ha", "cons2000":"140.02 ha", "cons2008":"64.85 ha", "auas":"0.00 ha", "app":"APP requirement 3.53 ha", "avn":"0.00 ha", "appd":"Pre-2008 APP restoration 3.17 ha", "app_auas":"0.00 ha"},
    }[spec["label"]]
    groups = [
        ("lr_layers", [("radam","RADAM vegetation formation","#1E6B52",True),("native","Native vegetation in 2024","#2E8B57",False),("secondary","Secondary vegetation scenario","#9FC65B",False)]),
        ("temporal_layers", [("cons2000","Cleared area by 2000","#B95B4C",False),("cons2008","Consolidated area by 2008","#D49A45",False),("auas","Post-2008 alternative land use","#7A4CA5",False)]),
        ("app_layers", [("app","Permanent Preservation Area (APP)","#2F80ED",False),("avn","Declared native vegetation (AVN)","#1E6B52",False),("appd","Pre-2008 APP liability (APPD)","#D49A45",False),("app_auas","Post-2008 clearing inside APP","#B95B4C",False)]),
    ]
    outputs = []
    for suffix, panels in groups:
        fig, axes = plt.subplots(1, len(panels), figsize=(15, 5.1), dpi=180)
        for ax, (key, title, color, categorical) in zip(axes, panels):
            draw_layer_panel(ax, prop, layers[key], title, reported[key], color, mosaic, extent, categorical)
        fig.text(.01, .012, "White/dark outline: CAR property boundary  |  Satellite: Esri World Imagery", fontsize=8, color="#5D716C")
        fig.tight_layout(rect=(0, .04, 1, 1), w_pad=1.2)
        target = OUT / f"{spec['label']}_{suffix}.png"
        fig.savefig(target, bbox_inches="tight", pad_inches=.04, facecolor="white")
        plt.close(fig)
        outputs.append(target)
    return outputs


if __name__ == "__main__":
    for example in EXAMPLES:
        print(render(example))
        for atlas in render_layer_atlases(example):
            print(atlas)
