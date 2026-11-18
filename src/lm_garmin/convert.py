"""S1: convert Topografi 50 GeoPackages to OSM PBF (one file per theme) for a region.

- Features are selected with the GeoPackage R-tree (bbox filter); geometries are not clipped.
- Read in Arrow batches, reprojected EPSG:3006 → 4326 vectorised.
- OSM ids are positive and ascending per object type, with one id range per theme so all
  theme files can be fed to splitter together.
- splitter needs nodes, then ways, then relations: ways and relations are buffered in
  temporary PBF files and appended at the end.
"""

from __future__ import annotations

import json
import os
import resource
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import osmium
import pyogrio
import shapely
from pyproj import Transformer

from . import __version__
from .region import Region
from .tags import SCHEMA_VERSION, feature_tags, read_columns

# Theme → layers, as delivered by Lantmäteriet (product version 2026.05).
# Fixed order → fixed id ranges. Never reorder; append new themes at the end.
THEME_LAYERS: dict[str, tuple[str, ...]] = {
    "administrativindelning": ("administrativ_grans", "riksrose"),
    "anlaggningsomrade": (
        "anlaggningsomrade",
        "anlaggningsomradespunkt",
        "flygplatsomrade",
        "flygplatspunkt",
        "start_landningsbana",
    ),
    "byggnadsverk": (
        "byggnad",
        "byggnadsanlaggningslinje",
        "byggnadsanlaggningspunkt",
        "byggnadspunkt",
    ),
    "hojd": ("hojdlinje", "hojdpunkt", "hojdkurvstext"),
    "hydrografi": (
        "hydroanlaggningslinje",
        "hydroanlaggningspunkt",
        "hydrografiskt_intressant_plats",
        "hydrolinje",
        "hydropunkt",
    ),
    "kommunikation": (
        "vaglinje",
        "vagpunkt",
        "farjeled",
        "ovrig_vag",
        "transportled_fjall",
        "ledintressepunkt_fjall",
        "ralstrafik",
        "ralstrafikstation",
    ),
    "kulturhistorisklamning": ("kultur_lamning_linje", "kultur_lamning_punkt"),
    "ledningar": ("ledningslinje", "transformatoromrade", "transformatoromradespunkt"),
    "mark": ("mark", "markkantlinje", "sankmark", "markframkomlighet"),
    "militartomrade": ("militart_omrade",),
    "naturvard": ("skyddadnatur", "naturvardspunkt", "naturvardslinje", "restriktionsomrade"),
    "norrapolcirkeln": ("polcirkeln",),
    "text": ("textpunkt", "textlinje"),
}
THEMES = list(THEME_LAYERS)
LAYER_THEME = {layer: theme for theme, layers in THEME_LAYERS.items() for layer in layers}
ID_STRIDE = 10**10  # ids of theme i are in [(i + 1) * ID_STRIDE, (i + 2) * ID_STRIDE)
BATCH_SIZE = 20_000


def id_base(theme: str) -> int:
    return (THEMES.index(theme) + 1) * ID_STRIDE


@dataclass
class ThemeStats:
    theme: str
    pbf: str
    features: int = 0
    nodes: int = 0
    ways: int = 0
    relations: int = 0
    seconds: float = 0.0
    max_rss_mb: float = 0.0
    layers: dict[str, int] = field(default_factory=dict)


class OsmSink:
    """Writes nodes immediately; buffers ways/relations so the output is correctly ordered."""

    def __init__(self, path: Path, base: int, bbox_wgs84: tuple[float, float, float, float]):
        self.path = path
        hdr = osmium.io.Header()
        hdr.set("generator", f"lm-garmin {__version__}")
        hdr.set("lm:tag-schema", str(SCHEMA_VERSION))
        hdr.add_box(
            osmium.osm.Box(
                osmium.osm.Location(*bbox_wgs84[:2]), osmium.osm.Location(*bbox_wgs84[2:])
            )
        )
        self._tmp_ways = path.with_suffix(".ways.tmp.pbf")
        self._tmp_rels = path.with_suffix(".rels.tmp.pbf")
        self.w = osmium.SimpleWriter(str(path), header=hdr, overwrite=True)
        self.ww = osmium.SimpleWriter(str(self._tmp_ways), overwrite=True)
        self.wr = osmium.SimpleWriter(str(self._tmp_rels), overwrite=True)
        self.next_node = self.next_way = self.next_rel = base
        self.nodes = self.ways = self.relations = 0

    def point(self, x: float, y: float, tags: dict[str, str]) -> None:
        self.w.add_node(osmium.osm.mutable.Node(id=self.next_node, location=(x, y), tags=tags))
        self.next_node += 1
        self.nodes += 1

    def _nodes(self, coords: np.ndarray, closed: bool) -> list[int]:
        n = len(coords) - 1 if closed else len(coords)
        first = self.next_node
        add = self.w.add_node
        Node = osmium.osm.mutable.Node
        for i in range(n):
            add(Node(id=first + i, location=(coords[i, 0], coords[i, 1])))
        self.next_node += n
        self.nodes += n
        ids = list(range(first, first + n))
        if closed:
            ids.append(first)
        return ids

    def way(self, coords: np.ndarray, tags: dict[str, str] | None, closed: bool = False) -> int:
        wid = self.next_way
        self.ww.add_way(
            osmium.osm.mutable.Way(id=wid, nodes=self._nodes(coords, closed), tags=tags or {})
        )
        self.next_way += 1
        self.ways += 1
        return wid

    def polygon(self, rings: list[np.ndarray], tags: dict[str, str]) -> None:
        if len(rings) == 1:
            self.way(rings[0], tags, closed=True)
            return
        members = [("w", self.way(rings[0], None, closed=True), "outer")]
        members += [("w", self.way(r, None, closed=True), "inner") for r in rings[1:]]
        self.wr.add_relation(
            osmium.osm.mutable.Relation(
                id=self.next_rel, members=members, tags={**tags, "type": "multipolygon"}
            )
        )
        self.next_rel += 1
        self.relations += 1

    def close(self) -> None:
        self.ww.close()
        self.wr.close()
        for tmp in (self._tmp_ways, self._tmp_rels):
            for obj in osmium.FileProcessor(str(tmp)):
                self.w.add(obj)
            tmp.unlink()
        self.w.close()


def _to_wgs84(geoms: np.ndarray, tr: Transformer) -> np.ndarray:
    def f(c: np.ndarray) -> np.ndarray:
        x, y = tr.transform(c[:, 0], c[:, 1])
        return np.column_stack([x, y])

    return shapely.transform(geoms, f)


def _write_batch(
    sink: OsmSink, layer: str, columns: list[str], batch, geom_col: str, tr: Transformer
) -> int:
    geoms = _to_wgs84(shapely.from_wkb(batch.column(geom_col).to_numpy(zero_copy_only=False)), tr)
    values = [batch.column(c).to_pylist() for c in columns]
    rows = list(zip(*values, strict=True)) if values else [()] * len(geoms)
    n = 0
    for g, row in zip(geoms, rows, strict=True):
        if g is None or g.is_empty:
            continue
        tags = feature_tags(layer, columns, row)
        n += 1
        for part in shapely.get_parts(g):
            t = shapely.get_type_id(part)
            if t == 0:  # Point
                sink.point(part.x, part.y, tags)
            elif t == 1:  # LineString
                sink.way(shapely.get_coordinates(part), tags)
            elif t == 3:  # Polygon
                rings = [shapely.get_coordinates(r) for r in shapely.get_rings(part)]
                sink.polygon(rings, tags)
    return n


def _max_rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(rss / (1e6 if os.uname().sysname == "Darwin" else 1e3), 1)


def convert_theme(
    theme: str, sources: list[tuple[Path, str]], region: Region, out_dir: Path
) -> ThemeStats:
    """Convert the given (gpkg, layer) pairs of one theme into <out_dir>/<theme>.osm.pbf."""
    t0 = time.monotonic()
    out = out_dir / f"{theme}.osm.pbf"
    tr = Transformer.from_crs(3006, 4326, always_xy=True)
    lon, lat = tr.transform([region.bbox[0], region.bbox[2]], [region.bbox[1], region.bbox[3]])
    stats = ThemeStats(theme, out.name)
    sink = OsmSink(out, id_base(theme), (lon[0], lat[0], lon[1], lat[1]))
    try:
        for gpkg, layer in sources:
            info = pyogrio.read_info(gpkg, layer=layer)
            columns = read_columns(list(info["fields"]))
            count = 0
            with pyogrio.raw.open_arrow(
                gpkg,
                layer=layer,
                columns=columns,
                bbox=region.bbox,
                batch_size=BATCH_SIZE,
                use_pyarrow=True,
            ) as (meta, reader):
                geom_col = meta["geometry_name"] or "wkb_geometry"
                for batch in reader:
                    count += _write_batch(sink, layer, columns, batch, geom_col, tr)
            stats.layers[layer] = stats.layers.get(layer, 0) + count
            stats.features += count
    finally:
        sink.close()
    stats.nodes, stats.ways, stats.relations = sink.nodes, sink.ways, sink.relations
    stats.seconds = round(time.monotonic() - t0, 2)
    stats.max_rss_mb = _max_rss_mb()
    return stats


def plan_sources(gpkg_dir: Path) -> dict[str, list[tuple[Path, str]]]:
    """Group the layers of all GeoPackages in a folder by theme.

    Works for Lantmäteriet's one-file-per-theme delivery as well as for fixtures that hold
    all themes in one file. Unknown layers are an error (no silent drops).
    """
    files = sorted(p for p in gpkg_dir.glob("*.gpkg") if not p.name.startswith("._"))
    if not files:
        raise FileNotFoundError(f"no *.gpkg in {gpkg_dir}")
    plan: dict[str, list[tuple[Path, str]]] = {}
    unknown = []
    for f in files:
        for layer, _ in pyogrio.list_layers(f):
            theme = LAYER_THEME.get(layer)
            if theme is None:
                unknown.append(f"{f.name}:{layer}")
            else:
                plan.setdefault(theme, []).append((f, layer))
    if unknown:
        raise ValueError(f"unknown layers (add them to THEME_LAYERS): {unknown}")
    return {t: plan[t] for t in THEMES if t in plan}


def convert(
    gpkg_dir: Path, region: Region, out_dir: Path, jobs: int | None = None, *, log=print
) -> list[ThemeStats]:
    """Convert all themes in parallel. Returns stats in theme order; writes convert-report.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = plan_sources(gpkg_dir)
    t0 = time.monotonic()

    def weight(theme: str) -> int:  # biggest first, so hojd/mark start immediately
        return -sum(p.stat().st_size for p, _ in plan[theme]) * len(plan[theme])

    with ProcessPoolExecutor(max_workers=jobs or os.cpu_count()) as ex:
        futures = {
            t: ex.submit(convert_theme, t, plan[t], region, out_dir)
            for t in sorted(plan, key=weight)
        }
        for t in sorted(plan, key=weight):
            s = futures[t].result()
            log(f"{s.theme}: {s.features} features, {s.nodes} nodes in {s.seconds}s")
    stats = [futures[t].result() for t in plan]
    report = {
        "lm_garmin": __version__,
        "tag_schema": SCHEMA_VERSION,
        "region": {"id": region.id, "bbox_3006": region.bbox},
        "seconds": round(time.monotonic() - t0, 2),
        "themes": [asdict(s) for s in stats],
    }
    (out_dir / "convert-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return stats
