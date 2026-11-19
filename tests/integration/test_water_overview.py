"""Check the built overview across a source-grid seam, including an island."""

import pyarrow as pa
import pyogrio
import pytest
import shapely
from pyproj import Transformer
from shapely.geometry import Point, box, shape

from lm_garmin import tools
from lm_garmin.build import build
from lm_garmin.region import Region
from lm_garmin.verify import decode
from lm_garmin.water_overview import merged_lakes

pytestmark = pytest.mark.integration


def test_lake_fragments_join_only_at_overview_levels(tmp_path):
    if not tools.find_java():
        pytest.skip("java not found")
    src = tmp_path / "src"
    src.mkdir()
    gpkg = src / "lakes.gpkg"
    region = Region("lake-test", (516000, 7270000, 524000, 7278000))
    lake = box(518000, 7271000, 522000, 7274000)
    island = box(519700, 7274800, 520300, 7275600)
    island_lake = box(518000, 7274400, 522000, 7276400).difference(island)
    west = box(516000, 7270000, 520000, 7278000)
    east = box(520000, 7270000, 524000, 7278000)
    ungrouped = box(516500, 7275500, 517500, 7276500)
    lakes = [lake.intersection(west), lake.intersection(east)]
    lakes += [island_lake.intersection(west), island_lake.intersection(east), ungrouped]
    pyogrio.write_arrow(
        pa.table(
            {
                "geom": [part.wkb for part in lakes],
                "objekttypnr": [2632] * len(lakes),
                "vattenytaid": ["lake", "lake", "island-lake", "island-lake", None],
            }
        ),
        gpkg,
        layer="mark",
        geometry_name="geom",
        geometry_type="Polygon",
        crs="EPSG:3006",
    )

    merged = merged_lakes([gpkg], region.bbox)
    assert merged.keys() == {"lake", "island-lake"}
    assert merged["lake"].equals(lake)
    assert merged["island-lake"].equals(island_lake)

    out = tmp_path / "out"
    build(src, region, out, tmp_path / "cache", products=["topo50"], jobs=1, java_mem="1g")
    project = Transformer.from_crs(4326, 3006, always_xy=True)
    decoded: dict[int, list] = {}
    for f in decode(out / "lm-topo50.img"):
        p = f["properties"]
        if p["kind"] == "polygon" and p["type"] == "0x3c":
            geom = shapely.transform(shape(f["geometry"]), project.transform, interleaved=False)
            decoded.setdefault(p["level"], []).append(geom)

    west_point = Point(519000, 7272500)
    east_point = Point(521000, 7272500)
    for level in range(6):
        polygons = decoded[level]
        assert any(g.covers(west_point) for g in polygons)
        assert any(g.covers(east_point) for g in polygons)
        assert any(g.covers(ungrouped.centroid) for g in polygons)
        assert all(not g.covers(island.centroid) for g in polygons)
        assert any(g.covers(west_point) and g.covers(east_point) for g in polygons) == (level == 4)
