"""Measure how much GPX track length lies near the built snowmobile overlay."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer
from pyproj.exceptions import ProjError
from shapely.geometry import LineString, shape

from .verify import decode

SAMPLE_INTERVAL_M = 5


class CoverageError(ValueError):
    pass


@dataclass(frozen=True)
class Coverage:
    track_m: float
    within_25m: float
    within_50m: float

    def __str__(self) -> str:
        return (
            f"GPX track length: {self.track_m / 1000:.1f} km\n"
            f"Within 25 m: {self.within_25m:.1%}\n"
            f"Within 50 m: {self.within_50m:.1%}"
        )


def gpx_files(path: Path) -> list[Path]:
    paths = sorted(path.iterdir()) if path.is_dir() else [path]
    return [
        file
        for file in paths
        if file.suffix.lower() == ".gpx" and not file.name.startswith(".") and file.is_file()
    ]


def _track_segments(files: list[Path], project: Transformer) -> Iterator[LineString]:
    for file in files:
        try:
            root = ET.parse(file).getroot()
            ns = root.tag.rpartition("}")[0] + "}" if root.tag.startswith("{") else ""
            if root.tag != f"{ns}gpx":
                raise ValueError
            for segment in root.iterfind(f"{ns}trk/{ns}trkseg"):
                coords = [
                    (float(point.attrib["lon"]), float(point.attrib["lat"]))
                    for point in segment.iterfind(f"{ns}trkpt")
                ]
                if any(not (-180 <= lon <= 180 and -90 <= lat <= 90) for lon, lat in coords):
                    raise ValueError
                if len(coords) >= 2:
                    x, y = project.transform(*zip(*coords, strict=True), errcheck=True)
                    yield LineString(np.column_stack((x, y)))
        except (ET.ParseError, OSError, KeyError, ValueError, ProjError):
            # Parser errors and filenames can contain private GPX data.
            raise CoverageError("Could not read a GPX file or its track coordinates.") from None


def measure(img: Path, gpx: Path) -> Coverage:
    """Estimate covered length with length-weighted midpoint samples at most 5 m apart."""
    files = gpx_files(gpx)
    if not files:
        raise CoverageError("No GPX files found. Supply a GPX file or a directory containing GPX.")
    if not img.is_file():
        raise CoverageError("Snowmobile overlay file not found.")

    project = Transformer.from_crs(4326, 3006, always_xy=True)
    lines = [
        shapely.transform(shape(f["geometry"]), project.transform, interleaved=False)
        for f in decode(img)
        if f["properties"]["kind"] == "line" and f["properties"]["level"] == 0
    ]
    index = shapely.STRtree(lines)
    track_m = within_25m = within_50m = 0.0
    for segment in _track_segments(files, project):
        length = segment.length
        if not length:
            continue
        count = math.ceil(length / SAMPLE_INTERVAL_M)
        weight = length / count
        samples = shapely.line_interpolate_point(segment, (np.arange(count) + 0.5) * weight)
        _, distances = index.query_nearest(
            samples, max_distance=50, return_distance=True, all_matches=False
        )
        within_25m += np.count_nonzero(distances <= 25) * weight
        within_50m += len(distances) * weight
        track_m += length

    if not track_m:
        raise CoverageError("GPX files contain no positive-length tracks.")
    return Coverage(track_m, within_25m / track_m, within_50m / track_m)
