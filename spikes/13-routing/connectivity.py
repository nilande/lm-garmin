"""How connected are Topografi 50 roads and paths? Endpoint/vertex coincidence per area (#28)."""

import sys
from collections import Counter

import numpy as np
import pyogrio
import shapely

GPKG = sys.argv[1]
AREAS = {
    "taby": (664000, 6584000, 680000, 6600000),
    "tarnaby": (490000, 7265000, 540000, 7315000),
}
LAYERS = {"vaglinje": "road", "ovrig_vag": "path", "farjeled": "ferry"}


def load(bbox):
    geoms, kinds, types = [], [], []
    for layer, kind in LAYERS.items():
        meta, _, wkb, fields = pyogrio.raw.read(GPKG, layer=layer, bbox=bbox, columns=["objekttypnr"])
        for g, t in zip(shapely.from_wkb(wkb), fields[0]):
            for part in shapely.get_parts(g):
                geoms.append(part)
                kinds.append(kind)
                types.append(int(t))
    return geoms, kinds, types


def key(xy, q):
    return tuple(np.round(np.asarray(xy) / q).astype(np.int64))


def main():
    for area, bbox in AREAS.items():
        geoms, kinds, types = load(bbox)
        coords = [shapely.get_coordinates(g) for g in geoms]
        # Vertex index at 1 mm (exact, after float noise) and at 0.5 m.
        exact: dict = {}
        for i, c in enumerate(coords):
            for j, xy in enumerate(c):
                exact.setdefault(key(xy, 0.001), set()).add(i)
        tree = shapely.STRtree(geoms)
        stats = Counter()
        by_kind = Counter()
        for i, c in enumerate(coords):
            for end in (c[0], c[-1]):
                k = kinds[i]
                others = exact.get(key(end, 0.001), set()) - {i}
                if others:
                    stats["shared_exact"] += 1
                    by_kind[(k, "shared_exact")] += 1
                    continue
                p = shapely.Point(end)
                near = [j for j in tree.query(p, predicate="dwithin", distance=1.0) if j != i]
                if not near:
                    stats["dead_end"] += 1
                    by_kind[(k, "dead_end")] += 1
                    continue
                d = min(shapely.distance(p, shapely.Point(xy)) for j in near for xy in coords[j])
                if d < 1.0:
                    stats["vertex_within_1m"] += 1
                    by_kind[(k, "vertex_within_1m")] += 1
                else:
                    stats["on_segment_no_vertex"] += 1
                    by_kind[(k, "on_segment_no_vertex")] += 1
        # Interior crossings between road/path lines without a shared vertex.
        crossings_shared = crossings_bare = 0
        pairs = tree.query(geoms, predicate="crosses")
        for a, b in zip(*pairs):
            if a < b:
                inter = shapely.intersection(geoms[a], geoms[b])
                for pt in shapely.get_coordinates(inter):
                    if exact.get(key(pt, 0.001), set()) >= {a, b}:
                        crossings_shared += 1
                    else:
                        crossings_bare += 1
        n = len(geoms)
        print(f"== {area}: {n} lines ({Counter(kinds)}) , {2 * n} endpoints")
        for s, v in stats.most_common():
            print(f"  {s:24s} {v:7d}  {v / (2 * n):6.1%}")
        for (k, s), v in sorted(by_kind.items()):
            print(f"    {k:6s} {s:24s} {v:7d}")
        print(f"  crossings shared vertex {crossings_shared}, without {crossings_bare}")


main()
