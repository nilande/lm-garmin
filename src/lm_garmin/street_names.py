"""Street names from Trafikverket NVDB for Topografi 50 roads (ADR-0007, issue #60).

Topografi 50 `vaglinje` has no street names. NVDB (Lastkajen, CC0) has them as name lines on
the same road network, which Topografi 50 is generalised from. Each Topografi 50 road
segment is matched geometrically:

1. NVDB name lines within `buffer` metres of the segment are candidates.
2. A candidate covers the parts of the segment inside its flat-capped buffer, but only where
   the two run in a similar direction (±`max_angle`), so crossing streets do not count.
3. Covered parts are projected onto the segment as intervals and unioned per name, so
   overlapping NVDB lines of one name are never counted twice.
4. Along the segment, each stretch gets the name that covers it (the name with the largest
   total cover wins where names overlap). Stretches shorter than `min_piece` are merged into
   a neighbour, so junction ends do not create slivers.
5. One name covering at least `min_share` of the segment names the whole segment. Otherwise
   the segment is split where the name changes; uncovered stretches stay unnamed.

All geometry is in SWEREF 99 TM (EPSG:3006), in metres.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyogrio
import shapely
from shapely.geometry import LineString
from shapely.ops import substring

GATUNAMN = "NVDB_DK_O_20_Gatunamn"
OVRIGT_VAGNAMN = "NVDB_DK_O_21_Ovrigt_vagnamn"
LAYERS = (GATUNAMN, OVRIGT_VAGNAMN)
NAME_FIELD = "Namn"
# Municipality and county of each name line (`nvdb extract` joins them from KommunLanReg):
# the "city" and "region" of a street for the device's address search (#72).
CITY_FIELD = "Kommun"
REGION_FIELD = "Lan"
TAG = "lm:gatunamn_nvdb"
CITY_TAG = "mkgmap:city"
REGION_TAG = "mkgmap:region"
COPYRIGHT = "Trafikverket (NVDB)"


@dataclass(frozen=True)
class Params:
    buffer: float = 15.0  # m
    max_angle: float = 30.0  # degrees
    min_share: float = 0.5  # of the segment length
    min_piece: float = 30.0  # m; shorter stretches merge into a neighbour
    ambiguous_share: float = 0.3  # overlap of two names that marks a segment as ambiguous


PARAMS = Params()


@dataclass
class Match:
    """Result for one segment: pieces in order along it, each with a name or None."""

    pieces: list[tuple[LineString, str | None]]
    ambiguous: bool = False

    @property
    def split(self) -> bool:
        return len(self.pieces) > 1


@dataclass
class MatchStats:
    segments: int = 0
    length: float = 0.0
    named_length: float = 0.0
    split_segments: int = 0
    ambiguous_segments: int = 0
    by_class: dict[str, list[float]] = field(default_factory=dict)  # t → [length, named]

    def add(self, t: str, length: float, named: float, m: Match) -> None:
        self.segments += 1
        self.length += length
        self.named_length += named
        self.split_segments += m.split
        self.ambiguous_segments += m.ambiguous
        c = self.by_class.setdefault(t, [0.0, 0.0])
        c[0] += length
        c[1] += named

    def as_dict(self) -> dict:
        return {
            "segments": self.segments,
            "km": round(self.length / 1000, 1),
            "named_share": round(self.named_length / self.length, 4) if self.length else 0.0,
            "split_segments": self.split_segments,
            "ambiguous_segments": self.ambiguous_segments,
            "named_share_by_class": {
                t: round(n / ln, 4) if ln else 0.0 for t, (ln, n) in sorted(self.by_class.items())
            },
        }


def bearing(coords: np.ndarray) -> float:
    """Undirected bearing (0–180°) from the first to the last coordinate."""
    dx, dy = coords[-1, 0] - coords[0, 0], coords[-1, 1] - coords[0, 1]
    return math.degrees(math.atan2(dy, dx)) % 180.0


def angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def sources(nvdb_dir: Path) -> list[Path]:
    """NVDB GeoPackages in a folder (one per county, or one for the whole country)."""
    files = sorted(p for p in nvdb_dir.glob("*.gpkg") if not p.name.startswith("._"))
    if not files:
        raise FileNotFoundError(f"no *.gpkg in {nvdb_dir}")
    for f in files:
        if GATUNAMN not in tables(f):
            raise ValueError(f"{f} has no layer {GATUNAMN} – is it an NVDB delivery?")
    return files


def provenance(files: list[Path]) -> dict:
    """Betraktelsedatum of the deliveries behind NVDB GeoPackages, from `nvdb extract` sidecars.

    Files without a sidecar (unpacked county GeoPackages) and sidecar sources without a date
    (FileGDB zips) are listed under `undated`.
    """
    dates: set[str] = set()
    undated: list[str] = []
    for f in files:
        sidecar = f.with_suffix(".json")
        if not sidecar.exists():
            undated.append(f.name)
            continue
        for s in json.loads(sidecar.read_text(encoding="utf-8")).get("sources", []):
            if s.get("betraktelsedatum"):
                dates.add(s["betraktelsedatum"])
            else:
                undated.append(s["file"])
    return {"betraktelsedatum": sorted(dates), "undated": undated}


def tables(gpkg: Path) -> set[str]:
    """Feature tables of a GeoPackage. (pyogrio.list_layers fails on some NVDB tables.)"""
    with sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True) as c:
        return {r[0] for r in c.execute("SELECT table_name FROM gpkg_contents")}


class NameIndex:
    """NVDB name lines of a region with a spatial index."""

    def __init__(
        self,
        lines: np.ndarray,
        names: list[str],
        params: Params = PARAMS,
        places: list[tuple[str, str] | None] | None = None,
    ):
        self.lines = lines
        self.names = names
        self.places = places or [None] * len(names)
        self.params = params
        self.tree = shapely.STRtree(lines)
        self._buffers: dict[int, object] = {}

    def __len__(self) -> int:
        return len(self.names)

    @classmethod
    def read(
        cls,
        paths: list[Path],
        bbox: tuple[float, float, float, float],
        params: Params = PARAMS,
    ) -> NameIndex:
        pad = params.buffer * 4
        area = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
        lines: list[np.ndarray] = []
        names: list[str] = []
        places: list[tuple[str, str] | None] = []
        seen: set[tuple[str, bytes]] = set()  # counties overlap at their borders
        for path in paths:
            available = tables(path)
            for layer in LAYERS:
                if layer not in available:
                    continue
                fields_here = set(pyogrio.read_info(path, layer=layer)["fields"])
                extra = [f for f in (CITY_FIELD, REGION_FIELD) if f in fields_here]
                meta, _, wkb, fields = pyogrio.raw.read(
                    path, layer=layer, bbox=area, columns=[NAME_FIELD, *extra]
                )
                if meta["crs"] != "EPSG:3006":
                    raise ValueError(f"{path}:{layer} must use SWEREF 99 TM (EPSG:3006)")
                if wkb is None or not len(wkb):
                    continue
                geoms = shapely.force_2d(shapely.from_wkb(wkb))
                cols = dict(zip(list(meta["fields"]), fields, strict=True))
                if len(extra) == 2:
                    where = [
                        (c, r) if c and r else None
                        for c, r in zip(cols[CITY_FIELD], cols[REGION_FIELD], strict=True)
                    ]
                else:
                    where = [None] * len(geoms)
                for geom, name, place in zip(geoms, cols[NAME_FIELD], where, strict=True):
                    name = (name or "").strip()
                    if geom is None or geom.is_empty or not name:
                        continue
                    for part in shapely.get_parts(geom):
                        k = (name, part.wkb)
                        if part.length > 0 and k not in seen:
                            seen.add(k)
                            lines.append(part)
                            names.append(name)
                            places.append(place)
        return cls(np.array(lines, dtype=object), names, params, places)

    def _buffer(self, i: int):
        b = self._buffers.get(i)
        if b is None:
            if len(self._buffers) > 200_000:
                self._buffers.clear()
            b = self._buffers[i] = shapely.buffer(
                self.lines[i], self.params.buffer, cap_style="flat"
            )
        return b

    def cover(self, line: LineString) -> dict[str, list[tuple[float, float]]]:
        """Unioned intervals (distance along `line`) covered by each candidate name."""
        p = self.params
        raw: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for i in self.tree.query(line, predicate="dwithin", distance=p.buffer):
            piece = shapely.intersection(line, self._buffer(int(i)))
            for part in shapely.get_parts(piece):
                if shapely.get_type_id(part) != 1 or part.length <= 0:
                    continue
                pc = shapely.get_coordinates(part)
                near = shapely.intersection(
                    self.lines[i], shapely.buffer(part, p.buffer, cap_style="flat")
                )
                nc = shapely.get_coordinates(near)
                if len(nc) < 2 or angle_diff(bearing(pc), bearing(nc)) > p.max_angle:
                    continue
                at = shapely.line_locate_point(line, shapely.points(pc))
                raw[self.names[i]].append((float(at.min()), float(at.max())))
        return {name: _union(iv) for name, iv in raw.items()}

    def place(self, piece: LineString, name: str) -> tuple[str, str] | None:
        """(municipality, county) of the nearest name line called `name` near `piece`."""
        mid = shapely.line_interpolate_point(piece, 0.5, normalized=True)
        best = None
        for i in self.tree.query(mid, predicate="dwithin", distance=self.params.buffer * 4):
            i = int(i)
            if self.names[i] == name and self.places[i] is not None:
                d = shapely.distance(self.lines[i], mid)
                if best is None or d < best[0]:
                    best = (d, self.places[i])
        return best[1] if best else None

    def match(self, line: LineString) -> Match:
        return assign(line, self.cover(line), self.params)


def _union(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out if b > a]


def _length(intervals: list[tuple[float, float]]) -> float:
    return sum(b - a for a, b in intervals)


def assign(
    line: LineString, cover: dict[str, list[tuple[float, float]]], params: Params = PARAMS
) -> Match:
    """Turn per-name cover intervals into named pieces of `line` (see module docstring)."""
    length = line.length
    if length <= 0 or not cover:
        return Match([(line, None)])
    total = {name: _length(iv) for name, iv in cover.items()}
    cuts = sorted({0.0, length, *(x for iv in cover.values() for a, b in iv for x in (a, b))})
    cuts = [x for x in cuts if 0.0 <= x <= length]

    # Elementary stretches: the covering name with the largest total cover wins.
    stretches: list[list] = []  # [start, end, name]
    overlap = 0.0
    for a, b in zip(cuts, cuts[1:], strict=False):
        if b - a <= 1e-9:
            continue
        mid = (a + b) / 2
        here = [n for n, iv in cover.items() if any(s <= mid <= e for s, e in iv)]
        if len(here) > 1:
            overlap += b - a
        name = max(here, key=lambda n: (total[n], n)) if here else None
        if stretches and stretches[-1][2] == name:
            stretches[-1][1] = b
        else:
            stretches.append([a, b, name])

    # Merge short stretches into the longer neighbour until all are long enough.
    while len(stretches) > 1:
        i = min(range(len(stretches)), key=lambda k: stretches[k][1] - stretches[k][0])
        if stretches[i][1] - stretches[i][0] >= params.min_piece:
            break
        left = stretches[i - 1] if i > 0 else None
        right = stretches[i + 1] if i + 1 < len(stretches) else None
        nb = (
            left
            if right is None or (left is not None and left[1] - left[0] >= right[1] - right[0])
            else right
        )
        nb[0], nb[1] = min(nb[0], stretches[i][0]), max(nb[1], stretches[i][1])
        del stretches[i]
        merged: list[list] = []
        for s in stretches:
            if merged and merged[-1][2] == s[2]:
                merged[-1][1] = s[1]
            else:
                merged.append(s)
        stretches = merged

    ambiguous = overlap >= params.ambiguous_share * length
    names = {s[2] for s in stretches if s[2] is not None}
    if len(stretches) == 1:
        return Match([(line, stretches[0][2])], ambiguous)
    if len(names) == 1:
        (only,) = names
        if total[only] >= params.min_share * length:
            return Match([(line, only)], ambiguous)
    pieces = [(substring(line, a, b), name) for a, b, name in stretches]
    return Match([(g, n) for g, n in pieces if g.length > 0], ambiguous)
