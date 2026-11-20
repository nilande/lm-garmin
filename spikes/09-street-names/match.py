"""SPIKE – not production code (issue #55).

Match NVDB street names (layer NVDB_DK_O_20_Gatunamn) to Topografi 50 `vaglinje` segments
in a bbox and report coverage, ambiguity and runtime.

For each Topografi 50 segment: NVDB lines within BUFFER m with a similar bearing are grouped
by name; the name whose buffers cover the largest share of the segment wins if it covers
≥ MIN_SHARE. Ambiguous = the runner-up covers ≥ AMBIG_SHARE.

Usage: uv run python spikes/09-street-names/match.py TOPO50_KOMMUNIKATION.gpkg NVDB.gpkg \
          xmin ymin xmax ymax [out.json]
"""

import collections
import json
import math
import os
import sys
import time

import numpy as np
import pyogrio
import shapely

BUFFER = float(os.environ.get("BUFFER", 15))
MAX_ANGLE = float(os.environ.get("MAX_ANGLE", 30))
MIN_SHARE = float(os.environ.get("MIN_SHARE", 0.6))
AMBIG_SHARE = 0.3
CLASSES = {1801: "Motorväg", 1802: "Motortrafikled", 1803: "Mötesfri väg", 1804: "Landsväg",
           1805: "Landsväg liten", 1806: "Småväg", 1807: "Småväg enkel standard",
           1808: "Övergripande länk", 1809: "Huvudgata", 1810: "Lokalgata stor",
           1811: "Lokalgata liten"}


def bearing(line) -> float:
    c = shapely.get_coordinates(line)
    dx, dy = c[-1, 0] - c[0, 0], c[-1, 1] - c[0, 1]
    return math.degrees(math.atan2(dy, dx)) % 180.0


def angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def main():
    topo, nvdb = sys.argv[1], sys.argv[2]
    bbox = tuple(float(v) for v in sys.argv[3:7])
    out = sys.argv[7] if len(sys.argv) > 7 else None
    t0 = time.monotonic()

    m, _, g, f = pyogrio.raw.read(topo, layer="vaglinje", bbox=bbox,
                                  columns=["objekttypnr", "vardvagnummer"])
    cls = f[0]
    roads = []
    for geom, c in zip(shapely.from_wkb(g), cls, strict=True):
        for part in shapely.get_parts(geom):
            roads.append((part, int(c)))

    pad = (bbox[0] - 50, bbox[1] - 50, bbox[2] + 50, bbox[3] + 50)
    m2, _, g2, f2 = pyogrio.raw.read(nvdb, layer="NVDB_DK_O_20_Gatunamn", bbox=pad,
                                     columns=["Namn"])
    nlines = shapely.force_2d(shapely.from_wkb(g2))
    names = f2[0]
    nb = [bearing(x) for x in nlines]
    buffers = shapely.buffer(nlines, BUFFER, cap_style="flat")
    tree = shapely.STRtree(buffers)
    t_read = time.monotonic() - t0

    stats = collections.defaultdict(lambda: collections.Counter())
    results = []
    for line, c in roads:
        L = line.length
        if L <= 0:
            continue
        rb = bearing(line)
        cover = collections.defaultdict(lambda: None)
        for i in tree.query(line):
            if angle_diff(rb, nb[i]) > MAX_ANGLE and line.length > 2 * BUFFER:
                continue
            piece = shapely.intersection(line, buffers[i])
            if piece.is_empty:
                continue
            prev = cover[names[i]]
            cover[names[i]] = piece if prev is None else shapely.union(prev, piece)
        shares = sorted(((v.length / L, k) for k, v in cover.items() if v is not None),
                        reverse=True)
        best = shares[0] if shares else (0.0, None)
        second = shares[1][0] if len(shares) > 1 else 0.0
        named = best[0] >= MIN_SHARE
        ambiguous = named and second >= AMBIG_SHARE
        s = stats[c]
        s["n"] += 1
        s["len"] += L
        if named:
            s["named_n"] += 1
            s["named_len"] += L
        if ambiguous:
            s["ambig_n"] += 1
        mid = line.interpolate(0.5, normalized=True)
        results.append({"class": c, "len": round(L, 1), "name": best[1] if named else None,
                        "share": round(best[0], 3), "second": round(second, 3),
                        "x": round(mid.x), "y": round(mid.y)})
    secs = time.monotonic() - t0

    print(f"bbox {bbox}: {len(roads)} Topografi 50 segments, {len(nlines)} NVDB name lines, "
          f"read {t_read:.1f}s, total {secs:.1f}s")
    print(f"{'class':<26}{'segments':>9}{'km':>8}{'named (len)':>13}{'ambiguous':>11}")
    tot = collections.Counter()
    for c in sorted(stats):
        s = stats[c]
        tot.update(s)
        print(f"{c} {CLASSES.get(c, ''):<21}{s['n']:>9}{s['len'] / 1000:>8.1f}"
              f"{s['named_len'] / s['len']:>12.1%}{s['ambig_n']:>11}")
    town = collections.Counter()
    for c in (1809, 1810, 1811):
        town.update(stats.get(c, {}))
    if town["len"]:
        print(f"town streets 1809–1811: {town['named_len'] / town['len']:.1%} of length named, "
              f"{town['ambig_n']} ambiguous of {town['n']}")
    print(f"all classes: {tot['named_len'] / tot['len']:.1%} of length named")
    if out:
        json.dump({"bbox": bbox, "seconds": round(secs, 1), "segments": results},
                  open(out, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
