"""Routable network: junction nodes for roads, paths and trails (#28).

mkgmap connects two lines for routing only where they share an OSM node, and merges road
pieces only there. The converter gives every line its own nodes, and Topografi 50 often has
no vertex where a path crosses a road or another path at ground level (Täby: 714 of 1 536
path–road crossings, Tärnaby: 156 of 180). Before the lines are written this module finds,
per 50 km grid cell:

- crossings and T-junctions between routable lines that are not a vertex of a line yet:
  the point is inserted into every line involved, except where a road is a bridge or tunnel
  (`bro_och_tunnel`);
- line ends that stop within `SNAP` metres of another routable line: the end is moved onto
  it and the point inserted there;
- every coordinate that more than one routable line passes through (`nodes`), so the sink
  writes one shared OSM node for it.

Coordinates are keyed on a 1 cm grid in SWEREF 99 TM (`key`).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pyogrio
import shapely

# Layers whose lines are part of the routable network.
LAYERS = ("vaglinje", "ovrig_vag", "cykelvaglinje", "farjeled")
# Path types that are not routable (winter-only trails cross lakes and bogs).
NOT_ROUTABLE = {"ovrig_vag": {1848}}
LEVEL = {None, "", "Ingen information"}  # bro_och_tunnel values of a road at ground level
SNAP = 1.0  # metres
ON_LINE = 0.01  # metres: a point closer than this to a line is on it
CELL = 50_000  # metres


def routable(layer: str, t: int | None) -> bool:
    return layer in LAYERS and t not in NOT_ROUTABLE.get(layer, ())


def key(xy: np.ndarray) -> np.ndarray:
    """int64 key of each coordinate (n × 2, EPSG:3006) on a 1 cm grid."""
    c = np.round(np.asarray(xy, dtype=np.float64).reshape(-1, 2) * 100).astype(np.int64)
    return (c[:, 0] << 31) | c[:, 1]


def unkey(k: np.ndarray) -> np.ndarray:
    return np.column_stack([k >> 31, k & ((1 << 31) - 1)]).astype(np.float64) / 100


def _line_key(layer: str, fid: int) -> int:
    return (LAYERS.index(layer) << 40) | fid


class Junctions:
    def __init__(self) -> None:
        # Points to insert per line (_line_key), EPSG:3006.
        self.points: dict[int, list[tuple[float, float]]] = defaultdict(list)
        self.nodes = np.empty(0, dtype=np.int64)  # sorted keys of shared coordinates
        self.inserted = 0
        self.snapped = 0

    def stats(self) -> dict[str, int]:
        return {"inserted": self.inserted, "snapped": self.snapped, "nodes": len(self.nodes)}

    @classmethod
    def find(cls, sources: list[tuple[Path, str]], bbox) -> Junctions:
        self = cls()
        sources = [(g, layer) for g, layer in sources if layer in LAYERS]
        chunks = []
        x0, y0, x1, y1 = bbox
        for cx in np.arange(np.floor(x0 / CELL) * CELL, x1, CELL):
            for cy in np.arange(np.floor(y0 / CELL) * CELL, y1, CELL):
                cell = (
                    float(max(cx, x0)),
                    float(max(cy, y0)),
                    float(min(cx + CELL, x1)),
                    float(min(cy + CELL, y1)),
                )
                keys, geoms, level = _read(sources, cell)
                if geoms:
                    chunks.append(self._cell(keys, geoms, level, cell))
        if chunks:
            self.nodes = np.unique(np.concatenate(chunks))
        return self

    @classmethod
    def of(cls, lines: list[tuple[str, int, object, bool]]) -> Junctions:
        """Junctions of in-memory lines (layer, fid, geometry, at ground level); for tests."""
        self = cls()
        keys = [_line_key(layer, fid) for layer, fid, _, _ in lines]
        geoms = [g for _, _, g, _ in lines]
        level = [lv for *_, lv in lines]
        b = shapely.total_bounds(geoms)
        self.nodes = np.unique(self._cell(keys, geoms, level, (b[0], b[1], b[2] + 1, b[3] + 1)))
        return self

    def _cell(self, keys, geoms, level, cell) -> np.ndarray:
        """Find the junctions inside one cell; returns the keys of its shared coordinates."""
        x0, y0, x1, y1 = cell

        def inside(p) -> bool:
            return x0 <= p[0] < x1 and y0 <= p[1] < y1

        arr = np.array(geoms, dtype=object)
        coords = [shapely.get_coordinates(g) for g in arr]
        tree = shapely.STRtree(arr)
        added: list[tuple[float, float]] = []

        def is_vertex(k: int, p) -> bool:
            return bool(np.any(np.all(np.abs(coords[k] - p) < ON_LINE, axis=1)))

        a, b = tree.query(arr, predicate="intersects")
        keep = a < b
        for i, j in zip(a[keep], b[keep], strict=True):
            parts = shapely.get_parts(shapely.intersection(arr[i], arr[j]))
            for p in shapely.get_coordinates(parts[shapely.get_type_id(parts) == 0]):
                if not inside(p):
                    continue
                on = [is_vertex(k, p) for k in (i, j)]
                if all(on):
                    continue
                ends = [
                    bool(np.all(np.abs(coords[k][e] - p) < ON_LINE))
                    for k in (i, j)
                    for e in (0, -1)
                ]
                if not any(ends) and not (level[i] and level[j]):
                    continue  # a crossing under or over a bridge
                for k, v in zip((i, j), on, strict=True):
                    if not v:
                        self.points[keys[k]].append((p[0], p[1]))
                added.append((p[0], p[1]))
                self.inserted += 1
        # Loose ends: move onto the nearest routable line within SNAP metres.
        for i, c in enumerate(coords):
            for end in (c[0], c[-1]):
                if not inside(end):
                    continue
                p = shapely.Point(end)
                near = [j for j in tree.query(p, predicate="dwithin", distance=SNAP) if j != i]
                if not near or any(shapely.distance(p, arr[j]) < ON_LINE for j in near):
                    continue
                j = min(near, key=lambda j: shapely.distance(p, arr[j]))
                q = shapely.get_coordinates(shapely.shortest_line(p, arr[j]))[1]
                self.points[keys[j]].append((q[0], q[1]))
                self.points[keys[i]].append((q[0], q[1]))  # the new end of line i
                added.append((q[0], q[1]))
                self.snapped += 1
        # Coordinates inside the cell that two or more lines pass through.
        per_line = [np.unique(key(c)) for c in coords]
        allk = np.concatenate(per_line)
        u, n = np.unique(allk, return_counts=True)
        shared = u[n > 1]
        xy = unkey(shared)
        shared = shared[(xy[:, 0] >= x0) & (xy[:, 0] < x1) & (xy[:, 1] >= y0) & (xy[:, 1] < y1)]
        return np.concatenate([shared, key(np.array(added))]) if added else shared

    def apply(self, layer: str, fid: int, g):
        """The line with its junction points inserted (ends moved when snapped)."""
        pts = self.points.get(_line_key(layer, fid))
        if not pts:
            return g
        if g.geom_type == "LineString":
            return _insert(g, pts)
        return shapely.MultiLineString([_insert(part, pts) for part in shapely.get_parts(g)])

    def shared(self, keys: np.ndarray) -> np.ndarray:
        """Index into `nodes` of each key, -1 where the coordinate is not shared."""
        idx = np.searchsorted(self.nodes, keys)
        idx[idx >= len(self.nodes)] = 0
        hit = len(self.nodes) > 0 and self.nodes[idx] == keys
        return np.where(hit, idx, -1)


def _read(sources, bbox):
    keys: list[int] = []
    geoms: list = []
    level: list[bool] = []
    for gpkg, layer in sources:
        info = pyogrio.read_info(gpkg, layer=layer)
        cols = ["objekttypnr"] + (["bro_och_tunnel"] if "bro_och_tunnel" in info["fields"] else [])
        _, fids, wkb, fields = pyogrio.raw.read(
            gpkg, layer=layer, bbox=bbox, columns=cols, return_fids=True
        )
        bridge = fields[1] if len(fields) > 1 else [None] * len(fids)
        for fid, g, t, b in zip(fids, shapely.from_wkb(wkb), fields[0], bridge, strict=True):
            if g is None or g.is_empty or not routable(layer, int(t)):
                continue
            for part in shapely.get_parts(g):
                keys.append(_line_key(layer, int(fid)))
                geoms.append(part)
                level.append(b in LEVEL)
    return keys, geoms, level


def _insert(line, pts: list[tuple[float, float]]):
    c = shapely.get_coordinates(line)
    pos = list(shapely.line_locate_point(line, shapely.points(c)))
    out = list(map(tuple, c))
    length = line.length
    for x, y in pts:
        p = shapely.Point(x, y)
        d = line.distance(p)
        if d > SNAP + ON_LINE:
            continue  # a point on another part of the feature
        s = line.project(p)
        if d >= ON_LINE:  # a snapped end of this line: move the nearer end
            out[0 if s < length / 2 else -1] = (x, y)
            continue
        near = [abs(s - q) for q in pos]
        if min(near) < ON_LINE:  # already a vertex here: make it exact
            out[int(np.argmin(near))] = (x, y)
            continue
        k = int(np.searchsorted(pos, s))
        out.insert(k, (x, y))
        pos.insert(k, s)
    return shapely.LineString(out)
