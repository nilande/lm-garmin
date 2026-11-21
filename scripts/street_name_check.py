"""Quality check of NVDB street names on Topografi 50 roads (issue #60).

Needs local data (not in CI):

    uv run python scripts/street_name_check.py \
        ~/.cache/lm-garmin/gpkg/kommunikation_sverige.gpkg ~/.cache/lm-garmin/nvdb/stockholm \
        [--area taby | --bbox xmin ymin xmax ymax] [--json out.json]

Reports the named share of road length per class and runs two checks:

1. Town streets (1809–1811): at least 90 % of the length is named.
2. A seeded sample of 100 named pieces: at a point `end` metres in from each end, the name
   of the nearest NVDB name line (within the match buffer) agrees with the assigned name.
   At most 2 disagreements are allowed.

Exit code 1 if a check fails.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import pyogrio
import shapely

from lm_garmin import street_names
from lm_garmin.region import AREAS

TOWN = ("1809", "1810", "1811")
TARGET_SHARE = 0.90
SAMPLE = 100
MAX_DISAGREE = 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kommunikation", type=Path, help="Topografi 50 kommunikation GeoPackage")
    ap.add_argument("nvdb_dir", type=Path, help="folder with NVDB GeoPackages")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--area", default="taby", choices=sorted(AREAS))
    g.add_argument("--bbox", type=float, nargs=4)
    ap.add_argument("--end", type=float, default=20.0, help="metres in from each end")
    ap.add_argument("--seed", type=int, default=60)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    bbox = tuple(a.bbox) if a.bbox else AREAS[a.area]

    t0 = time.monotonic()
    index = street_names.NameIndex.read(street_names.sources(a.nvdb_dir), bbox)
    t_read = time.monotonic() - t0
    _, _, wkb, fields = pyogrio.raw.read(
        a.kommunikation, layer="vaglinje", bbox=bbox, columns=["objekttypnr"]
    )
    stats = street_names.MatchStats()
    named: list[tuple[str, object, str]] = []
    for geom, t in zip(shapely.from_wkb(wkb), fields[0], strict=True):
        for line in shapely.get_parts(geom):
            m = index.match(line)
            n = sum(g.length for g, name in m.pieces if name)
            stats.add(str(int(t)), line.length, n, m)
            named += [(str(int(t)), g, name) for g, name in m.pieces if name]
    secs = time.monotonic() - t0

    town_len = sum(stats.by_class.get(t, [0, 0])[0] for t in TOWN)
    town_named = sum(stats.by_class.get(t, [0, 0])[1] for t in TOWN)
    share = town_named / town_len if town_len else 0.0

    rng = random.Random(a.seed)
    pool = [x for x in named if x[0] in TOWN]
    sample = rng.sample(pool, min(SAMPLE, len(pool)))
    disagree = []
    for t, g, name in sample:
        d = min(a.end, g.length / 4)
        got = []
        for p in (g.interpolate(d), g.interpolate(g.length - d)):
            hits = index.tree.query_nearest(p, max_distance=index.params.buffer, all_matches=True)
            got.append({index.names[i] for i in hits})
        if not all(name in s for s in got):
            mid = g.interpolate(0.5, normalized=True)
            disagree.append(
                {
                    "class": t,
                    "name": name,
                    "ends": [sorted(s) for s in got],
                    "x": round(mid.x),
                    "y": round(mid.y),
                }
            )

    result = {
        "bbox": bbox,
        "nvdb_lines": len(index),
        "seconds": {"read_nvdb": round(t_read, 1), "total": round(secs, 1)},
        "params": street_names.PARAMS.__dict__,
        **stats.as_dict(),
        "town_streets": {"km": round(town_len / 1000, 1), "named_share": round(share, 4)},
        "sample": {"size": len(sample), "disagree": len(disagree), "cases": disagree},
    }
    print(f"bbox {bbox}: {stats.segments} segments, {len(index)} NVDB name lines, {secs:.1f} s")
    for t, s in result["named_share_by_class"].items():
        print(f"  {t}: {stats.by_class[t][0] / 1000:7.1f} km  {s:6.1%} named")
    print(f"split {stats.split_segments}, ambiguous {stats.ambiguous_segments}")
    ok1 = share >= TARGET_SHARE
    ok2 = len(disagree) <= MAX_DISAGREE
    print(
        f"[{'ok' if ok1 else 'FAIL'}] town streets 1809–1811: {share:.1%} named "
        f"(target ≥ {TARGET_SHARE:.0%})"
    )
    print(
        f"[{'ok' if ok2 else 'FAIL'}] sample: {len(disagree)} of {len(sample)} disagree "
        f"with the nearest NVDB name at an end (max {MAX_DISAGREE})"
    )
    for c in disagree:
        print(f"    {c}")
    if a.json:
        a.json.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if ok1 and ok2 else 1


if __name__ == "__main__":
    sys.exit(main())
