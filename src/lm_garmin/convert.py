"""S1: convert Topografi 50 GeoPackages to OSM PBF (one file per theme) for a region.

- Features are selected with the GeoPackage R-tree (bbox filter). For a named region (county,
  municipality) features that cross its boundary are cut at it; a bbox region and Sweden
  are not clipped.
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
from tempfile import TemporaryFile

import numpy as np
import osmium
import pyogrio
import shapely
from pyproj import Transformer

from . import __version__, street_names
from .forest_overview import FOREST_TYPE, merged_forests
from .region import Region
from .tags import ALIASES, SCHEMA_VERSION, feature_tags, read_columns, tag_key
from .water_overview import LAKE_TYPE, merged_lakes

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
        "cykelvaglinje",  # 2027.05: cycle paths (1623) moved here from ovrig_vag (#56)
    ),
    "kulturhistorisklamning": ("kultur_lamning_linje", "kultur_lamning_punkt"),
    "ledningar": ("ledningslinje", "transformatoromrade", "transformatoromradespunkt"),
    "mark": ("mark", "markkantlinje", "sankmark", "markframkomlighet"),
    "militartomrade": ("militart_omrade",),
    "naturvard": ("skyddadnatur", "naturvardspunkt", "naturvardslinje", "restriktionsomrade"),
    "norrapolcirkeln": ("polcirkeln",),
    "text": ("textpunkt", "textlinje"),
}
# Layers of Topografi 50 2027.05 (from 2027-05-04) that the current delivery lacks (#56).
LAYERS_2027 = frozenset({"cykelvaglinje"})
THEMES = list(THEME_LAYERS)
LAYER_THEME = {layer: theme for theme, layers in THEME_LAYERS.items() for layer in layers}
ID_STRIDE = 10**10  # ids of theme i are in [(i + 1) * ID_STRIDE, (i + 2) * ID_STRIDE)
BATCH_SIZE = 20_000
# Built-up land cover (mark): sluten, hög, låg bebyggelse, industri- och handelsbebyggelse.
BUILTUP_TYPES = (2636, 2637, 2638, 2639)
BUILTUP_TAG = "lm:i_bebyggelse"
# Tags the converter adds itself; the others come from source columns (tags.py).
GENERATED_TAGS = frozenset({"lm:ov", BUILTUP_TAG, "lm:gatunamn_nvdb"})


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
    merged_lakes: int = 0
    merged_forests: int = 0
    street_names: dict = field(default_factory=dict)


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


def clip_to_region(geoms: np.ndarray, area) -> np.ndarray:
    """Cut features that cross a named region's boundary; drop those outside.

    Only parts of the feature's own dimension are kept (a polygon cut along the boundary
    must not leave stray lines or points). Features inside are returned unchanged.
    """
    keep = shapely.intersects(area, geoms)
    geoms = geoms.copy()
    geoms[~keep] = None
    cross = keep & ~shapely.within(geoms, area)
    if cross.any():
        dims = shapely.get_dimensions(geoms[cross])
        cut = shapely.intersection(geoms[cross], area)
        geoms[cross] = [
            shapely.geometrycollections(
                [q for q in shapely.get_parts(c) if shapely.get_dimensions(q) == d]
            )
            for c, d in zip(cut, dims, strict=True)
        ]
    return geoms


def _write_batch(
    sink: OsmSink,
    layer: str,
    columns: list[str],
    batch,
    geom_col: str,
    tr: Transformer,
    lake_ids: frozenset[str],
    forest_fids: set[int],
    fid_col: str,
    region: Region,
    names: street_names.NameIndex | None = None,
    name_stats: street_names.MatchStats | None = None,
    builtup: shapely.STRtree | None = None,
) -> int:
    geoms = shapely.from_wkb(batch.column(geom_col).to_numpy(zero_copy_only=False))
    if region.geometry is not None:
        geoms = clip_to_region(geoms, region.geometry)
        keep = ~shapely.is_missing(geoms) & ~shapely.is_empty(geoms)
        geoms = geoms[keep]
        batch = batch.filter(keep)
    if names is not None and layer == "vaglinje":
        return _write_named_roads(sink, layer, columns, batch, geoms, tr, names, name_stats)
    inside = np.zeros(len(geoms), dtype=bool)
    if builtup is not None and len(geoms):
        inside[builtup.query(geoms, predicate="within")[0]] = True
    geoms = _to_wgs84(geoms, tr)
    values = [batch.column(c).to_pylist() for c in columns]
    rows = list(zip(*values, strict=True)) if values else [()] * len(geoms)
    n = 0
    fids = batch.column(fid_col).to_pylist() if forest_fids else [None] * len(geoms)
    for g, row, fid, built in zip(geoms, rows, fids, inside, strict=True):
        if g is None or g.is_empty:
            continue
        tags = feature_tags(layer, columns, row)
        if built:
            tags[BUILTUP_TAG] = "yes"
        if fid in forest_fids or (
            lake_ids and tags.get("lm:t") == LAKE_TYPE and tags.get("lm:vattenytaid") in lake_ids
        ):
            tags["lm:ov"] = "detail"
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


def _write_named_roads(
    sink: OsmSink,
    layer: str,
    columns: list[str],
    batch,
    geoms: np.ndarray,
    tr: Transformer,
    names: street_names.NameIndex,
    stats: street_names.MatchStats,
) -> int:
    """Roads with NVDB street names: match in EPSG:3006, split where the name changes."""
    values = [batch.column(c).to_pylist() for c in columns]
    n = 0
    for g, row in zip(geoms, zip(*values, strict=True), strict=True):
        if g is None or g.is_empty:
            continue
        tags = feature_tags(layer, columns, row)
        n += 1
        for part in shapely.get_parts(g):
            m = names.match(part)
            named = sum(p.length for p, nm in m.pieces if nm)
            stats.add(tags.get("lm:t", ""), part.length, named, m)
            for piece, name in m.pieces:
                t = {**tags, street_names.TAG: name} if name else tags
                place = names.place(piece, name) if name else None
                if place:
                    t = {**t, street_names.CITY_TAG: place[0], street_names.REGION_TAG: place[1]}
                sink.way(shapely.get_coordinates(_to_wgs84(piece, tr)), t)
    return n


def builtup_index(mark: list[Path], region: Region) -> shapely.STRtree | None:
    """Built-up land-cover polygons of the region, to tag map texts inside towns."""
    polygons = []
    where = f"objekttypnr IN ({', '.join(map(str, BUILTUP_TYPES))})"
    for gpkg in mark:
        _, _, wkb, _ = pyogrio.raw.read(
            gpkg, layer="mark", bbox=region.bbox, where=where, columns=[]
        )
        if wkb is not None and len(wkb):
            polygons.extend(shapely.get_parts(shapely.from_wkb(wkb)))
    return shapely.STRtree(polygons) if polygons else None


def _max_rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(rss / (1e6 if os.uname().sysname == "Darwin" else 1e3), 1)


def convert_theme(
    theme: str,
    sources: list[tuple[Path, str]],
    region: Region,
    out_dir: Path,
    nvdb: list[Path] | None = None,
    mark: list[Path] | None = None,
) -> ThemeStats:
    """Convert the given (gpkg, layer) pairs of one theme into <out_dir>/<theme>.osm.pbf."""
    t0 = time.monotonic()
    out = out_dir / f"{theme}.osm.pbf"
    tr = Transformer.from_crs(3006, 4326, always_xy=True)
    lon, lat = tr.transform([region.bbox[0], region.bbox[2]], [region.bbox[1], region.bbox[3]])
    stats = ThemeStats(theme, out.name)
    if region.geometry is not None:
        shapely.prepare(region.geometry)
    names = name_stats = None
    if nvdb and any(layer == "vaglinje" for _, layer in sources):
        names = street_names.NameIndex.read(nvdb, region.bbox)
        name_stats = street_names.MatchStats()
    builtup = None
    if mark and any(layer == "textpunkt" for _, layer in sources):
        builtup = builtup_index(mark, region)
    with TemporaryFile(dir=out_dir) as forest_overviews:
        sink = OsmSink(out, id_base(theme), (lon[0], lat[0], lon[1], lat[1]))
        try:
            lakes = merged_lakes(
                [gpkg for gpkg, layer in sources if layer == "mark"], region.bbox, region.geometry
            )
            lake_ids = frozenset(lakes)
            for gpkg, layer in sources:
                info = pyogrio.read_info(gpkg, layer=layer)
                columns = read_columns(list(info["fields"]))
                forest_fids: set[int] = set()
                if layer == "mark":
                    for fids, forest in merged_forests(gpkg, region.bbox, region.geometry):
                        forest_fids.update(fids)
                        # Keep merged shapes on disk until the detailed features are written.
                        wkb = forest.wkb
                        forest_overviews.write(len(wkb).to_bytes(4, "little"))
                        forest_overviews.write(wkb)
                        stats.merged_forests += 1
                count = 0
                with pyogrio.raw.open_arrow(
                    gpkg,
                    layer=layer,
                    columns=columns,
                    bbox=region.bbox,
                    batch_size=BATCH_SIZE,
                    use_pyarrow=True,
                    return_fids=bool(forest_fids),
                ) as (meta, reader):
                    geom_col = meta["geometry_name"] or "wkb_geometry"
                    for batch in reader:
                        count += _write_batch(
                            sink,
                            layer,
                            columns,
                            batch,
                            geom_col,
                            tr,
                            lake_ids if layer == "mark" else frozenset(),
                            forest_fids,
                            meta["fid_column"],
                            region,
                            names,
                            name_stats,
                            builtup if layer == "textpunkt" else None,
                        )
                stats.layers[layer] = stats.layers.get(layer, 0) + count
                stats.features += count
            if region.geometry is not None:
                cut = clip_to_region(np.array(list(lakes.values()), dtype=object), region.geometry)
                lakes = {
                    k: g
                    for k, g in zip(lakes, cut, strict=True)
                    if g is not None and not g.is_empty
                }
            for water_id, lake in sorted(lakes.items()):
                tags = {
                    "lm:l": "mark",
                    "lm:t": LAKE_TYPE,
                    "lm:vattenytaid": water_id,
                    "lm:ov": "yes",
                }
                for part in shapely.get_parts(_to_wgs84(lake, tr)):
                    sink.polygon(
                        [shapely.get_coordinates(r) for r in shapely.get_rings(part)], tags
                    )
            stats.merged_lakes = len(lakes)
            forest_tags = {"lm:l": "mark", "lm:t": FOREST_TYPE, "lm:ov": "yes"}
            forest_overviews.seek(0)
            for _ in range(stats.merged_forests):
                size = int.from_bytes(forest_overviews.read(4), "little")
                forest = shapely.from_wkb(forest_overviews.read(size))
                if region.geometry is not None:
                    forest = clip_to_region(np.array([forest], dtype=object), region.geometry)[0]
                if forest is None or forest.is_empty:
                    continue
                for part in shapely.get_parts(_to_wgs84(forest, tr)):
                    sink.polygon(
                        [shapely.get_coordinates(r) for r in shapely.get_rings(part)], forest_tags
                    )
        finally:
            sink.close()
    if name_stats is not None:
        stats.street_names = {"nvdb_lines": len(names), **name_stats.as_dict()}
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


def missing_columns(gpkg_dir: Path, needed: dict[str, set[str]]) -> dict[str, list[str]]:
    """Tags a style reads that no source column of the layer provides (#56).

    Lantmäteriet's 2027 test data dropped `vardvagnummer` from `vaglinje`: every road number
    would vanish without an error. Layers absent from the delivery are not reported.
    """
    found: dict[str, set[str]] = {}
    for files in plan_sources(gpkg_dir).values():
        for f, layer in files:
            cols = pyogrio.read_info(f, layer=layer)["fields"]
            have = found.setdefault(layer, set())
            have.update(tag_key(c) for c in cols)
            have.update(ALIASES[c] for c in cols if c in ALIASES)
    out = {}
    for layer, tags in needed.items():
        if layer in found:
            missing = sorted(t for t in tags - GENERATED_TAGS if t not in found[layer])
            if missing:
                out[layer] = missing
    return out


def convert(
    gpkg_dir: Path,
    region: Region,
    out_dir: Path,
    jobs: int | None = None,
    *,
    log=print,
    nvdb: list[Path] | None = None,
) -> list[ThemeStats]:
    """Convert all themes in parallel. Returns stats in theme order; writes convert-report.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = plan_sources(gpkg_dir)
    t0 = time.monotonic()
    mark = [gpkg for gpkg, layer in plan.get("mark", []) if layer == "mark"]

    def weight(theme: str) -> int:  # biggest first, so hojd/mark start immediately
        return -sum(p.stat().st_size for p, _ in plan[theme]) * len(plan[theme])

    with ProcessPoolExecutor(max_workers=jobs or os.cpu_count()) as ex:
        futures = {
            t: ex.submit(convert_theme, t, plan[t], region, out_dir, nvdb, mark)
            for t in sorted(plan, key=weight)
        }
        for t in sorted(plan, key=weight):
            s = futures[t].result()
            log(f"{s.theme}: {s.features} features, {s.nodes} nodes in {s.seconds}s")
            if s.street_names:
                sn = s.street_names
                log(f"  street names: {sn['named_share']:.1%} of {sn['km']} km road named")
    stats = [futures[t].result() for t in plan]
    report = {
        "lm_garmin": __version__,
        "tag_schema": SCHEMA_VERSION,
        "region": {"id": region.id, "bbox_3006": region.bbox},
        "nvdb": [p.name for p in nvdb or []],
        "seconds": round(time.monotonic() - t0, 2),
        "themes": [asdict(s) for s in stats],
    }
    (out_dir / "convert-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return stats
