"""Regions to build: a bounding box in SWEREF 99 TM (EPSG:3006)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon

Bbox = tuple[float, float, float, float]


@dataclass(frozen=True)
class Region:
    name: str
    bbox: Bbox  # xmin, ymin, xmax, ymax in EPSG:3006
    geometry: Polygon | MultiPolygon | None = None
    boundary_source: str | None = None

    @property
    def id(self) -> str:
        """Stable id for cache paths."""
        if self.name:
            return self.name
        return "bbox-" + "-".join(str(round(v)) for v in self.bbox)


# Named areas for quick development builds (EPSG:3006).
AREAS: dict[str, Bbox] = {
    # Täby/Enebyberg/Sätra: town streets, built-up areas, lakes (contains the tatort fixture)
    "taby": (665000, 6585000, 680000, 6600000),
    # Hemavan–Syter and the lake country south of Lövlund: mountains, Sami names, snowmobile trails
    "hemavan": (500000, 7260000, 525000, 7310000),
}


def from_area(name: str) -> Region:
    if name not in AREAS:
        raise ValueError(f"unknown area {name!r}; known: {', '.join(sorted(AREAS))}")
    return Region(name, AREAS[name])


def parse_bbox(text: str) -> Bbox:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError(f"bbox needs 4 comma-separated numbers, got {text!r}")
    xmin, ymin, xmax, ymax = (float(p) for p in parts)
    if xmin >= xmax or ymin >= ymax:
        raise ValueError(f"bbox must be xmin,ymin,xmax,ymax with min < max, got {text!r}")
    return xmin, ymin, xmax, ymax


def from_bbox(text: str) -> Region:
    return Region("", parse_bbox(text))


def from_wgs84(text: str) -> Region:
    """lon_min,lat_min,lon_max,lat_max → enclosing EPSG:3006 bbox (edges densified)."""
    lon0, lat0, lon1, lat1 = parse_bbox(text)
    t = np.linspace(0.0, 1.0, 21)
    lon = np.concatenate(
        [
            lon0 + (lon1 - lon0) * t,
            np.full_like(t, lon1),
            lon1 - (lon1 - lon0) * t,
            np.full_like(t, lon0),
        ]
    )
    lat = np.concatenate(
        [
            np.full_like(t, lat0),
            lat0 + (lat1 - lat0) * t,
            np.full_like(t, lat1),
            lat1 - (lat1 - lat0) * t,
        ]
    )
    x, y = Transformer.from_crs(4326, 3006, always_xy=True).transform(lon, lat)
    return Region("", (float(x.min()), float(y.min()), float(x.max()), float(y.max())))


def sweden(gpkg_dir: Path) -> Region:
    """Union of the extents in gpkg_contents of all themes (uttag.json's bbox is unreliable)."""
    boxes = []
    for g in sorted(gpkg_dir.glob("*.gpkg")):
        if g.name.startswith("._"):
            continue
        with sqlite3.connect(f"file:{g}?mode=ro", uri=True) as c:
            boxes += c.execute(
                "SELECT min_x, min_y, max_x, max_y FROM gpkg_contents WHERE min_x IS NOT NULL"
            ).fetchall()
    if not boxes:
        raise FileNotFoundError(f"no GeoPackages with extents in {gpkg_dir}")
    a = np.asarray(boxes, dtype=float)
    return Region("sweden", (a[:, 0].min(), a[:, 1].min(), a[:, 2].max(), a[:, 3].max()))
