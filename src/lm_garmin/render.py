"""Inspect the appearance of decoded Garmin features against a georeferenced raster."""

from __future__ import annotations

import json
import warnings
from collections import defaultdict
from math import ceil, isfinite
from pathlib import Path

import numpy as np
import rasterio
import shapely
from pyproj import Transformer
from rasterio.enums import ColorInterp
from rasterio.errors import NotGeoreferencedWarning
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from shapely.geometry import box, shape

from .products import PRODUCTS
from .region import Bbox
from .stylegen import _pattern, load, typ_rules
from .verify import decode, norm_type

CRS = "EPSG:3006"
# Keep this palette independent of the Garmin style so style changes don't alter the reference.
PALETTE = {
    "background": ("#FFFFFF", "#F0F0F0"),
    "water": ("#CBEAFF",),
    "coniferous_mixed_forest": ("#D4EEB7",),
    "deciduous_forest": ("#C7D9B3",),
    "mountain_birch_forest": ("#DFF5D9",),
    "open_ground": ("#FFFFEA",),
    "open_mountain": ("#FFFFF2",),
    "field": ("#FFF7A6",),
    "built_up": ("#D58B5B", "#E6B28C", "#F2CF9B", "#E0E0E0"),
    "wetland": ("#E88A2E", "#40BAFF"),
    "glacier": ("#F4FAFF",),
}
TYPE_CLASSES = {
    0x01: "built_up",
    0x02: "built_up",
    0x03: "built_up",
    0x0C: "built_up",
    0x28: "water",
    0x3C: "water",
    0x48: "water",
    0x3F: "water",
    0x50: "coniferous_mixed_forest",
    0x10F01: "deciduous_forest",
    0x10F02: "mountain_birch_forest",
    0x10F03: "open_ground",
    0x52: "open_mountain",
    0x4E: "field",
    0x10F08: "field",
    0x51: "wetland",
    0x10F04: "wetland",
    0x4D: "glacier",
}
CLASS_IDS = {name: i for i, name in enumerate(PALETTE, 1)}
PALETTE_DISTANCE = 18
MAX_PIXELS = 100_000_000  # 50 km square at 5 m/px.


def _rgb(colour: str) -> tuple[int, ...]:
    return tuple(bytes.fromhex(colour.removeprefix("#")))


def _save_png(path: Path, rgb: np.ndarray) -> None:
    height, width, _ = rgb.shape
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with rasterio.open(
            path, "w", driver="PNG", width=width, height=height, count=3, dtype="uint8"
        ) as target:
            target.write(np.moveaxis(rgb, -1, 0))


def _classify(rgb: np.ndarray) -> np.ndarray:
    """Assign the closest reference colour within the distance threshold."""
    classes = np.zeros(rgb.shape[:2], dtype=np.uint8)
    for start in range(0, len(rgb), 128):
        pixels = rgb[start : start + 128].astype(np.int16)
        dest = classes[start : start + 128]
        best = np.full(dest.shape, PALETTE_DISTANCE**2 + 1, dtype=np.int32)
        for cls, colours in PALETTE.items():
            for colour in colours:
                delta = pixels - np.array(_rgb(colour), dtype=np.int16)
                distance = np.einsum("...i,...i->...", delta, delta, dtype=np.int32)
                closer = distance < best
                best[closer] = distance[closer]
                dest[closer] = CLASS_IDS[cls]
    return classes


def _draw(img, rules, level, bounds, transform, size, metres):
    project = Transformer.from_crs(4326, CRS, always_xy=True)
    window = box(*bounds).buffer(20 * metres)
    layers = defaultdict(list)
    for feature in decode(img):
        p = feature["properties"]
        kind, code = p["kind"], p["type"]
        style = rules.get((kind, code))
        if p["level"] != level or style is None or not style.colour:
            continue
        geometry = shapely.transform(
            shape(feature["geometry"]), project.transform, interleaved=False
        )
        if geometry.intersects(window):
            layers[kind, code].append(geometry)
    if not layers:
        raise ValueError(f"No styled features at level {level} in the requested bounds")

    rgb = np.full((*size, 3), 255, dtype=np.uint8)
    classes = np.full(size, CLASS_IDS["background"], dtype=np.uint8)
    # TYP draws by ascending polygon order. Stable sort retains the order within each group.
    polygons = sorted(
        (key for key in layers if key[0] == "polygon"),
        key=lambda key: int(rules[key].order or 1),
    )

    def mask(geoms):
        return geometry_mask(geoms, size, transform, invert=True)

    for key in polygons:
        rule = rules[key]
        covered = mask(layers[key])
        classified = covered
        colour = rule.colour
        if rule.pattern not in ("", "solid"):
            pattern = np.array([list(row) for row in _pattern(rule.pattern)])
            rows, columns = np.ogrid[: size[0], : size[1]]
            foreground = pattern[rows % len(pattern), columns % pattern.shape[1]] == "a"
            if rule.colour2:
                rgb[covered & ~foreground] = _rgb(rule.colour)
                colour = rule.colour2
            covered = covered & foreground
            if not rule.colour2:
                classified = covered
        rgb[covered] = _rgb(colour)
        if name := TYPE_CLASSES.get(int(rule.type, 16)):
            classes[classified] = CLASS_IDS[name]

    for key in sorted(layers, key=lambda key: key[0] == "point"):
        kind, _ = key
        if kind == "polygon":
            continue
        geometries = layers[key]
        rule = rules[key]
        if kind == "point":
            half = int(rule.width or 5) * metres / 2
            shapes = [box(g.x - half, g.y - half, g.x + half, g.y + half) for g in geometries]
        else:
            width = int(rule.width or 1)
            if rule.colour2 and rule.pattern == "solid":
                border = shapely.buffer(geometries, (width + 2) * metres / 2)
                rgb[mask(border)] = _rgb(rule.colour2)
            shapes = shapely.buffer(geometries, width * metres / 2)
        rgb[mask(shapes)] = _rgb(rule.colour)
    return rgb, classes


def run(
    img: Path,
    out: Path,
    *,
    bbox: Bbox | None = None,
    reference: Path | None = None,
    level: int = 0,
    metres: float = 5,
    mapping: Path | None = None,
) -> dict | None:
    if bbox is None:
        if reference is None:
            raise ValueError("Specify --bbox or --reference")
        with rasterio.open(reference) as src:
            if not src.crs:
                raise ValueError("The reference raster must be georeferenced")
            bbox = transform_bounds(src.crs, CRS, *src.bounds)
    if not isfinite(metres) or metres <= 0 or not all(map(isfinite, bbox)):
        raise ValueError(
            "Bounds and metres per pixel must be finite and pixel size must be positive"
        )
    xmin, ymin, xmax, ymax = bbox
    width, height = ceil((xmax - xmin) / metres), ceil((ymax - ymin) / metres)
    if min(width, height) < 1 or width * height > MAX_PIXELS:
        raise ValueError("Choose a smaller extent or larger pixel size (limit 100 million pixels)")
    transform = from_origin(xmin, ymax, metres, metres)
    rules = {
        (kind, norm_type(code)): rule
        for (kind, code), rule in typ_rules(
            load(mapping or PRODUCTS["topo50"].style_dir / "mapping.csv")
        ).items()
    }
    rendered, predicted = _draw(img, rules, level, bbox, transform, (height, width), metres)
    out.mkdir(parents=True, exist_ok=True)
    _save_png(out / "render.png", rendered)
    if reference is None:
        return None

    with rasterio.open(reference) as src:
        if not src.crs or src.count < 3 or any(dtype != "uint8" for dtype in src.dtypes[:3]):
            raise ValueError("The reference must be a georeferenced 8-bit RGB raster")
        with WarpedVRT(
            src,
            crs=CRS,
            transform=transform,
            width=width,
            height=height,
            add_alpha=ColorInterp.alpha not in src.colorinterp,
        ) as vrt:
            original = np.moveaxis(vrt.read([1, 2, 3]), 0, -1)
            valid = vrt.dataset_mask() != 0
    expected = _classify(original)
    compared = valid & (expected != 0)
    if not compared.any():
        raise ValueError("No classifiable reference pixels overlap the output grid")
    metrics = {}
    for name, cls in CLASS_IDS.items():
        if name == "background":
            continue
        a, b = (expected == cls) & compared, (predicted == cls) & compared
        intersection = int(np.count_nonzero(a & b))
        union = int(np.count_nonzero(a | b))
        metrics[name] = {
            "intersection_pixels": intersection,
            "union_pixels": union,
            "iou": round(intersection / union, 6) if union else None,
        }
    diff = original // 2 + 100
    diff[~compared] = (210, 210, 210)
    diff[compared & (expected != predicted)] = (196, 46, 54)
    _save_png(out / "side-by-side.png", np.concatenate((original, rendered), axis=1))
    _save_png(out / "diff.png", diff)
    report = {
        "bbox_3006": [xmin, ymax - height * metres, xmin + width * metres, ymax],
        "level": level,
        "metres_per_pixel": metres,
        "width": width,
        "height": height,
        "reference_pixels": int(valid.sum()),
        "classified_pixels": int(compared.sum()),
        "classes": metrics,
    }
    (out / "comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
