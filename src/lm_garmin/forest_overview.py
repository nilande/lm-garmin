"""Dissolve coniferous and mixed forest across the Topografi 50 source grid."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pyogrio
import shapely
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon, Polygon

from .region import Bbox

FOREST_TYPE = "2645"
SOURCE_GRID_M = 10_000
BLOCK_M = 50_000
GRID_TOLERANCE_M = 0.01


def _components(geoms: np.ndarray, cells: np.ndarray) -> Iterator[list[int]]:
    """Find pieces linked by edges across source cells inside the current block."""
    links: dict[int, list[int]] = defaultdict(list)
    left, right = shapely.STRtree(geoms).query(geoms, predicate="intersects")
    candidates = (left < right) & np.any(cells[left] != cells[right], axis=1)
    left, right = left[candidates], right[candidates]
    try:
        shared_edges = shapely.relate_pattern(geoms[left], geoms[right], "****1****")
    except GEOSException:
        return  # A topology error leaves the block's original polygons in the style.
    for a, b in zip(left[shared_edges].tolist(), right[shared_edges].tolist(), strict=True):
        links[a].append(b)
        links[b].append(a)
    while links:
        pending = [next(iter(links))]
        group = []
        while pending:
            index = pending.pop()
            if index in links:
                pending.extend(links.pop(index))
                group.append(index)
        yield sorted(group)


def merged_forests(path: Path, bbox: Bbox) -> Iterator[tuple[list[int], Polygon | MultiPolygon]]:
    """Yield source feature IDs and their valid union, one 50 km block at a time."""
    info = pyogrio.read_info(path, layer="mark")
    if "objekttypnr" not in info["fields"]:
        return
    xmin, ymin, xmax, ymax = bbox
    if info["total_bounds"] is not None:
        a, b, c, d = info["total_bounds"]
        xmin, ymin, xmax, ymax = max(xmin, a), max(ymin, b), min(xmax, c), min(ymax, d)
    if xmin >= xmax or ymin >= ymax:
        return
    for x in range(
        math.floor(xmin / BLOCK_M) * BLOCK_M, math.ceil(xmax / BLOCK_M) * BLOCK_M, BLOCK_M
    ):
        for y in range(
            math.floor(ymin / BLOCK_M) * BLOCK_M, math.ceil(ymax / BLOCK_M) * BLOCK_M, BLOCK_M
        ):
            window = (max(xmin, x), max(ymin, y), min(xmax, x + BLOCK_M), min(ymax, y + BLOCK_M))
            meta, data = pyogrio.read_arrow(
                path,
                layer="mark",
                bbox=window,
                where=f"objekttypnr = {FOREST_TYPE}",
                columns=[],
                return_fids=True,
            )
            if data.num_rows < 2:
                continue
            ids = data[meta["fid_column"]].to_numpy()
            geom_col = meta["geometry_name"] or "wkb_geometry"
            geoms = shapely.from_wkb(data[geom_col].to_pylist())
            bounds = shapely.bounds(geoms)
            centres = (bounds[:, :2] + bounds[:, 2:]) / 2
            owned = np.all((centres >= (x, y)) & (centres < (x + BLOCK_M, y + BLOCK_M)), axis=1)
            grid = np.rint(bounds / SOURCE_GRID_M) * SOURCE_GRID_M
            touches_grid = np.any(np.abs(bounds - grid) <= GRID_TOLERANCE_M, axis=1)
            keep = owned & touches_grid
            ids, geoms, centres = ids[keep], geoms[keep], centres[keep]
            valid = shapely.is_valid(geoms) & ~shapely.is_empty(geoms)
            ids, geoms = ids[valid], geoms[valid]
            cells = np.floor(centres[valid] / SOURCE_GRID_M)
            for component in _components(geoms, cells):
                parts = shapely.get_parts(geoms[component])
                try:
                    forest = shapely.union_all(parts)
                except GEOSException:
                    continue
                if (
                    isinstance(forest, (Polygon, MultiPolygon))
                    and not forest.is_empty
                    and forest.is_valid
                    and shapely.get_num_geometries(forest) < len(parts)
                ):
                    yield ids[component].tolist(), forest
