"""Write a synthetic snowmobile-overlay test grid for a device check (issue #57).

Eight north–south trails – ovrig_vag 1847 and 1848 × skoterkörning tillåten Ja, Påbjuden,
Nej, Ingen information – with three 1836 markers, a labelled header per trail, and
synthetic wetland bands (sankmark fast and våt) under part of each trail, so every status
can be judged over the real background, over firm and over wet wetland hatching.

The output is one GeoPackage that is added next to the real Topografi 50 files, e.g.:

    uv run python scripts/make_overlay_testgrid.py --center 673560,6594600 \
        --out /tmp/grid/overlay_testgrid.gpkg
    mkdir -p /tmp/gpkg && ln -sf ~/.cache/lm-garmin/gpkg/*.gpkg /tmp/grid/*.gpkg /tmp/gpkg/
    uv run lm-garmin build --gpkg-dir /tmp/gpkg --area taby --dev --out dist/dev

Test data only: never ship a map built with it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow as pa
import pyogrio
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, box

STATUSES = ("Ja", "Påbjuden", "Nej", "Ingen information")
SHORT = {"Ja": "Ja", "Påbjuden": "Påbj", "Nej": "Nej", "Ingen information": "Ingen"}


def write(path: Path, layer: str, geoms: list, geometry_type: str, **columns) -> None:
    table = pa.table({"geom": [g.wkb for g in geoms], **columns})
    pyogrio.write_arrow(
        table,
        path,
        layer=layer,
        geometry_name="geom",
        geometry_type=geometry_type,
        crs="EPSG:3006",
        append=path.exists(),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--center", required=True, help="E,N in SWEREF 99 TM")
    ap.add_argument("--spacing", type=float, default=70.0, help="metres between trails")
    ap.add_argument("--length", type=float, default=600.0, help="trail length in metres")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    cx, cy = (float(v) for v in a.center.split(","))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.unlink(missing_ok=True)

    half = a.length / 2
    combos = [(t, s) for t in (1847, 1848) for s in STATUSES]
    x0 = cx - a.spacing * (len(combos) - 1) / 2
    xs = [x0 + i * a.spacing for i in range(len(combos))]
    third = a.length / 3

    trails = [MultiLineString([LineString([(x, cy - half), (x, cy + half)])]) for x in xs]
    write(
        a.out,
        "ovrig_vag",
        trails,
        "MultiLineString",
        objekttypnr=[t for t, _ in combos],
        skoterkorning_tillaten=[s for _, s in combos],
    )
    # 1836 markers along the 1847 Påbjuden trail (the second one).
    marks = [Point(xs[1], cy - half + f * a.length) for f in (0.15, 0.5, 0.85)]
    write(a.out, "ledintressepunkt_fjall", marks, "Point", objekttypnr=[1836] * 3)
    # Bottom third over sankmark våt, middle third over sankmark fast, top third real ground.
    xmin, xmax = xs[0] - a.spacing / 2, xs[-1] + a.spacing / 2
    wet = MultiPolygon([box(xmin, cy - half, xmax, cy - half + third)])
    firm = MultiPolygon([box(xmin, cy - half + third, xmax, cy - half + 2 * third)])
    write(a.out, "sankmark", [firm, wet], "MultiPolygon", objekttypnr=[2651, 2652])
    labels = [Point(x, cy + half + 25) for x in xs]
    write(
        a.out,
        "textpunkt",
        labels,
        "Point",
        textstrang=[f"{t} {SHORT[s]}" for t, s in combos],
        textkategori=["Terrängnamn"] * len(combos),
        textstorleksklass=["2"] * len(combos),
        textdelnr=[0] * len(combos),
    )
    print(f"{a.out}: {len(trails)} trails, {len(marks)} markers, x {xs[0]:.0f}–{xs[-1]:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
