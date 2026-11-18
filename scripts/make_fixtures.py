"""Re-create the test fixtures in tests/data from a Topografi 50 delivery.

Run with the project environment (needs pyogrio/shapely) and the GDAL command line tool
gdal_translate for the raster cut-outs:

    uv run python scripts/make_fixtures.py \
        --gpkg-dir ~/.cache/lm-garmin/gpkg \
        --raster-dir "/Volumes/scratch/lm-kartdata/raster 1-50k" \
        --delivery-id "LM2026:173692"

Every fixture is a clip of all layers of all themes into one GeoPackage. Features are
selected with the R-tree index and cut to the bbox with shapely.clip_by_rect; only parts
with the layer's own dimension are kept (a contour touching the edge does not become a
point). Where a 1:50 000 raster exists, a cut-out of the reference raster is written too.
PROVENANCE.md is (re)written with bboxes, method, data dates and checksums.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyogrio
import shapely

OUT = Path(__file__).resolve().parent.parent / "tests" / "data"


@dataclass(frozen=True)
class Fixture:
    name: str
    bbox: tuple[int, int, int, int]  # xmin, ymin, xmax, ymax in EPSG:3006
    raster: str | None  # 1:50 000 raster file that contains the bbox
    why: str


FIXTURES = [
    Fixture(
        "fjall_727_51_05",
        (515000, 7270000, 520000, 7275000),
        "72_5_50.tif",
        "mountain area; same extent as the 1:10 000 reference 727_51_05",
    ),
    Fixture(
        "tatort_659_67_00",
        (670000, 6590000, 675000, 6595000),
        "65_6_55.tif",
        "urban area and archipelago; same extent as the 1:10 000 reference 659_67_00",
    ),
    Fixture(
        "skoter_730_51",
        (510000, 7300000, 520000, 7310000),
        None,
        "smallest window with all 8 combinations of ovrig_vag 1847/1848 x "
        "skoterkorning_tillaten, plus 3 points of type 1836",
    ),
]

DIMENSION = {"POINT": 0, "LINESTRING": 1, "POLYGON": 2}
OGR_MULTI = {0: "MultiPoint", 1: "MultiLineString", 2: "MultiPolygon"}


def theme_files(gpkg_dir: Path) -> list[Path]:
    return sorted(p for p in gpkg_dir.glob("*.gpkg") if not p.name.startswith("._"))


def layers(gpkg: Path) -> list[tuple[str, str]]:
    """(table, geometry type) for every feature table, e.g. ("hojdlinje", "MULTILINESTRING")."""
    with sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True) as c:
        rows = c.execute(
            "SELECT table_name, geometry_type_name FROM gpkg_geometry_columns ORDER BY table_name"
        ).fetchall()
    return [(t, g.upper()) for t, g in rows]


def data_date(gpkg_dir: Path) -> str:
    dates: set[str] = set()
    for g in theme_files(gpkg_dir):
        with sqlite3.connect(f"file:{g}?mode=ro", uri=True) as c:
            dates |= {r[0][:10] for r in c.execute("SELECT last_change FROM gpkg_contents")}
    return ", ".join(sorted(dates))


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def clip_geometries(geoms: np.ndarray, bbox: tuple[int, ...], dim: int) -> np.ndarray:
    """Clip to bbox, keep only parts of dimension `dim`, return multi-geometries (or None)."""
    clipped = shapely.clip_by_rect(geoms, *bbox)
    out = np.empty(len(clipped), dtype=object)
    for i, g in enumerate(clipped):
        parts = [p for p in shapely.get_parts(g) if shapely.get_dimensions(p) == dim]
        parts = [q for p in parts for q in shapely.get_parts(p)]  # flatten nested multis
        if not parts:
            out[i] = None
        elif dim == 0:
            out[i] = shapely.multipoints(parts)
        elif dim == 1:
            out[i] = shapely.multilinestrings(parts)
        else:
            out[i] = shapely.multipolygons(parts)
    return out


def clip_vector(fx: Fixture, gpkg_dir: Path) -> Path:
    out = OUT / f"{fx.name}.gpkg"
    out.unlink(missing_ok=True)
    for g in theme_files(gpkg_dir):
        for layer, gtype in layers(g):
            meta, _, wkb, fields = pyogrio.raw.read(g, layer=layer, bbox=fx.bbox)
            dim = DIMENSION[gtype.removeprefix("MULTI")]
            geoms = clip_geometries(shapely.from_wkb(wkb), fx.bbox, dim)
            keep = np.array([x is not None and not x.is_empty for x in geoms], dtype=bool)
            pyogrio.raw.write(
                out,
                geometry=shapely.to_wkb(geoms[keep]) if keep.any() else np.array([], dtype=object),
                field_data=[np.asarray(f)[keep] for f in fields],
                fields=meta["fields"],
                layer=layer,
                driver="GPKG",
                geometry_type=OGR_MULTI[dim],
                crs=meta["crs"],
                append=out.exists(),
            )
    return out


def clip_raster(fx: Fixture, raster_dir: Path) -> Path | None:
    if not fx.raster:
        return None
    src = raster_dir / fx.raster
    out = OUT / f"{fx.name}.ref50k.tif"
    xmin, ymin, xmax, ymax = fx.bbox
    subprocess.run(
        [
            "gdal_translate",
            "-q",
            "-projwin",
            str(xmin),
            str(ymax),
            str(xmax),
            str(ymin),
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "PREDICTOR=2",
            "-co",
            "TILED=YES",
            str(src),
            str(out),
        ],
        check=True,
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--gpkg-dir", type=Path, required=True, help="unpacked Topografi 50 themes")
    ap.add_argument("--raster-dir", type=Path, help="folder with Karta 1:50 000 GeoTIFFs")
    ap.add_argument(
        "--delivery-id", default="unknown", help="Geotorget order id, e.g. LM2026:173692"
    )
    a = ap.parse_args()

    if not theme_files(a.gpkg_dir):
        sys.exit(f"no *.gpkg in {a.gpkg_dir}")
    OUT.mkdir(parents=True, exist_ok=True)

    rows = []
    for fx in FIXTURES:
        v = clip_vector(fx, a.gpkg_dir)
        r = clip_raster(fx, a.raster_dir) if a.raster_dir else None
        for p in (v, r):
            if p:
                rows.append((p.name, fx, p.stat().st_size, sha256(p)))
        print(f"{fx.name}: {v.stat().st_size / 1e6:.1f} MB" + (f", raster {r.name}" if r else ""))

    lines = [
        "# Test data provenance",
        "",
        "Generated by `scripts/make_fixtures.py` – do not edit by hand.",
        "",
        "- Source: Lantmäteriet, *Topografi 50 Nedladdning, vektor* (CC0) and "
        "*Karta 1:50 000 Nedladdning, raster* (CC0). © Lantmäteriet.",
        f"- Delivery: `{a.delivery_id}`, data dated {data_date(a.gpkg_dir)}",
        f"- Generated: {dt.date.today().isoformat()}",
        "- Vector: every layer of every theme; features selected by R-tree, cut with "
        "`shapely.clip_by_rect`, only parts of the layer's own dimension kept; EPSG:3006.",
        "- Raster: `gdal_translate -projwin <bbox>` from the 1:50 000 GeoTIFF (5 m/px), DEFLATE.",
        "",
        "| File | Bbox (EPSG:3006) | Purpose | Bytes | SHA-256 |",
        "|---|---|---|---:|---|",
    ]
    for name, fx, size, h in rows:
        bbox = f"E {fx.bbox[0]}–{fx.bbox[2]}, N {fx.bbox[1]}–{fx.bbox[3]}"
        lines.append(f"| `{name}` | {bbox} | {fx.why} | {size} | `{h[:16]}…` |")
    lines += [
        "",
        "`tracks/ci_handmade.gpx` is a synthetic test track (see its header); it is **not** "
        "Skoterleder.org data.",
        "",
    ]
    (OUT / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
