"""Prepare the optional OpenStreetMap supplement in SWEREF 99 TM."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import osmium
import pyogrio
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, box
from shapely.ops import substring

from .convert import OsmSink, plan_sources
from .region import Region

ACCESS_VALUES = ("yes", "designated", "permissive")
MATCH_DISTANCE_M = 40
MATCH_LENGTH_M = 120
MIN_REMAINDER_M = 30


def read_trails(source: Path, filtered: Path) -> list[tuple[LineString, dict[str, str]]]:
    """Read tagged ways and their nodes without indexing every node in the source."""
    ways = osmium.FileProcessor(str(source), osmium.osm.WAY).with_filter(
        osmium.filter.TagFilter(*(("snowmobile", value) for value in ACCESS_VALUES))
    )
    with osmium.BackReferenceWriter(str(filtered), ref_src=str(source), overwrite=True) as writer:
        for way in ways:
            # Pistes mapped as areas do not describe a navigable centreline.
            if way.tags.get("area") != "yes":
                writer.add(way)

    project = Transformer.from_crs(4326, 3006, always_xy=True)
    trails = []
    ways_with_locations = (
        osmium.FileProcessor(str(filtered))
        .with_locations()
        .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
    )
    for way in ways_with_locations:
        try:
            coords = [(node.lon, node.lat) for node in way.nodes]
        except osmium.InvalidLocationError as e:
            raise ValueError(f"OSM way {way.id} is missing nodes. Use a complete extract.") from e
        if len(coords) < 2:
            continue
        x, y = project.transform(*zip(*coords, strict=True), errcheck=True)
        line = LineString(np.column_stack((x, y)))
        if line.length:
            tags = {
                key: way.tags[key] for key in ("snowmobile", "ice_road", "name") if key in way.tags
            }
            trails.append((line, {**tags, "lm:l": "osm_skoter"}))
    return trails


def reference_lines(gpkg_dir: Path, region: Region) -> shapely.STRtree:
    """Include all LM winter trails, including ones marked closed to snowmobiles."""
    bounds = box(*region.bbox).buffer(MATCH_DISTANCE_M).bounds
    lines = []
    for gpkg, layer in plan_sources(gpkg_dir).get("kommunikation", []):
        if layer == "ovrig_vag":
            meta, table = pyogrio.read_arrow(
                gpkg, layer=layer, bbox=bounds, columns=[], where="objekttypnr IN (1847, 1848)"
            )
            lines.extend(
                shapely.get_parts(shapely.from_wkb(table[meta["geometry_name"]].to_pylist()))
            )
    return shapely.STRtree(lines)


def unmatched(line: LineString, reference: shapely.STRtree) -> list[LineString]:
    """Keep stretches outside LM trail corridors, ignoring brief crossings."""
    candidates = reference.query(line, predicate="dwithin", distance=MATCH_DISTANCE_M)
    if not len(candidates):
        return [line]
    corridor = shapely.union_all(
        shapely.buffer(reference.geometries.take(candidates), MATCH_DISTANCE_M)
    )
    # Use linear positions so a short crossing elsewhere on the same way stays connected.
    overlaps = []
    for part in shapely.get_parts(line.intersection(corridor)):
        if part.length >= min(MATCH_LENGTH_M, 0.8 * line.length):
            start = line.project(shapely.get_point(part, 0))
            end = line.project(shapely.get_point(part, -1))
            overlaps.append((min(start, end), max(start, end)))
    if not overlaps:
        return [line]
    if line.difference(corridor).is_empty:
        return []
    if not line.is_simple or line.is_ring:
        return [
            p for p in shapely.get_parts(line.difference(corridor)) if p.length >= MIN_REMAINDER_M
        ]
    result = []
    cursor = 0.0
    for start, end in sorted(overlaps):
        if start - cursor >= MIN_REMAINDER_M:
            result.append(substring(line, cursor, start))
        cursor = max(cursor, end)
    if line.length - cursor >= MIN_REMAINDER_M:
        result.append(substring(line, cursor, line.length))
    return result


def write_region(
    trails: list[tuple[LineString, dict[str, str]]], gpkg_dir: Path, region: Region, out: Path
) -> int:
    reference = reference_lines(gpkg_dir, region)
    extent = box(*region.bbox)
    project = Transformer.from_crs(3006, 4326, always_xy=True)
    sink = OsmSink(out, 1, project.transform_bounds(*region.bbox))
    try:
        for line, tags in trails:
            if not line.intersects(extent):
                continue
            for part in shapely.get_parts(line.intersection(extent)):
                if part.geom_type == "LineString" and part.length:
                    for remaining in unmatched(part, reference):
                        wgs84 = shapely.transform(remaining, project.transform, interleaved=False)
                        sink.way(shapely.get_coordinates(wgs84), tags)
    finally:
        sink.close()
    return sink.ways
