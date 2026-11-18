# /// script
# requires-python = ">=3.12"
# dependencies = ["shapely>=2.0", "pyproj>=3.6", "numpy"]
# ///
"""SPIKE – not production code.

Share of GPX track length that lies within X m of a snowmobile object
decoded from a built Garmin .img (GeoJSON lines from ImgDump.java).

Usage: uv run coverage.py decoded.geojsonl gpx_dir [tolerances...]
"""
import glob
import json
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import shapely
from pyproj import Transformer

TR = Transformer.from_crs(4326, 3006, always_xy=True)
NS = {"g": "http://www.topografix.com/GPX/1/1"}
STEP = 5.0  # metres between sample points along the GPX tracks


def load_gpx(d):
    lines = []
    for f in sorted(glob.glob(os.path.join(d, "*.gpx"))):
        if os.path.basename(f).startswith("._"):
            continue
        root = ET.parse(f).getroot()
        for seg in root.iterfind(".//g:trkseg", NS):
            pts = [(float(p.get("lon")), float(p.get("lat"))) for p in seg.iterfind("g:trkpt", NS)]
            if len(pts) >= 2:
                x, y = TR.transform(*zip(*pts))
                lines.append(shapely.LineString(np.column_stack([x, y])))
    return lines


def load_decoded(path, kinds=("line",)):
    geoms, types = [], []
    for l in open(path, encoding="utf-8"):
        f = json.loads(l)
        if f["properties"]["kind"] not in kinds or f["properties"]["level"] != 0:
            continue
        c = np.asarray(f["geometry"]["coordinates"])
        x, y = TR.transform(c[:, 0], c[:, 1])
        geoms.append(shapely.LineString(np.column_stack([x, y])))
        types.append(f["properties"]["type"])
    return geoms, types


def main():
    dec, gpx_dir = sys.argv[1], sys.argv[2]
    tols = [float(t) for t in sys.argv[3:]] or [25.0, 50.0]
    tracks = load_gpx(gpx_dir)
    total = sum(t.length for t in tracks)
    geoms, types = load_decoded(dec)
    tree = shapely.STRtree(geoms)
    samples, weights = [], []
    for t in tracks:
        n = max(int(t.length // STEP), 1)
        d = (np.arange(n) + 0.5) * (t.length / n)
        samples.append(shapely.line_interpolate_point(t, d))
        weights.append(np.full(n, t.length / n))
    pts = np.concatenate(samples)
    w = np.concatenate(weights)
    print(f"GPX: {len(tracks)} tracks, {total / 1000:.0f} km; decoded skoter lines: {len(geoms)}")
    for tol in tols:
        idx, dist = tree.query_nearest(pts, max_distance=tol, return_distance=True, all_matches=False)
        hit = np.zeros(len(pts), bool)
        hit[idx[0]] = True
        print(f"within {tol:>4.0f} m: {w[hit].sum() / total:.1%} ({w[hit].sum() / 1000:.0f} km)")


if __name__ == "__main__":
    main()
