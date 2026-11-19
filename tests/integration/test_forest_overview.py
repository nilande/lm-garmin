"""Verify forest dissolution and the surrounding land cover in the compiled map."""

import pyarrow as pa
import pyogrio
import pytest
import shapely
from pyproj import Transformer
from shapely.geometry import Point, box, shape

from lm_garmin import tools
from lm_garmin.build import build
from lm_garmin.forest_overview import merged_forests
from lm_garmin.region import Region
from lm_garmin.verify import decode

pytestmark = pytest.mark.integration


def test_forest_overview_joins_grid_fragments_and_keeps_clearings(tmp_path):
    if not tools.find_java():
        pytest.skip("java not found")
    src = tmp_path / "src"
    src.mkdir()
    gpkg = src / "mark.gpkg"
    region = Region("forest-test", (516000, 7270000, 524000, 7279000))
    west = box(516000, 7270000, 520000, 7279000)
    east = box(520000, 7270000, 524000, 7279000)
    plain = box(518000, 7271000, 522000, 7273300)
    lake = box(519500, 7275000, 520500, 7276000)
    clearing = box(521000, 7275600, 522000, 7276600)
    forest = box(517000, 7274200, 523000, 7277800).difference(lake.union(clearing))
    fragments = [part.intersection(side) for part in (plain, forest) for side in (west, east)]
    pyogrio.write_arrow(
        pa.table(
            {
                "geom": [g.wkb for g in [*fragments, lake, clearing]],
                "objekttypnr": [2645, 2645, 2645, 2645, 2632, 2640],
            }
        ),
        gpkg,
        layer="mark",
        geometry_name="geom",
        geometry_type="Polygon",
        crs="EPSG:3006",
    )

    groups = list(merged_forests(gpkg, region.bbox))
    assert len(groups) == 2
    assert all(len(fids) == 2 for fids, _ in groups)
    assert any(geom.equals(plain) for _, geom in groups)
    assert any(geom.equals(forest) for _, geom in groups)

    out = tmp_path / "out"
    build(src, region, out, tmp_path / "cache", products=["topo50"], jobs=1, java_mem="1g")
    project = Transformer.from_crs(4326, 3006, always_xy=True)
    west_point, east_point = Point(519000, 7272000), Point(521000, 7272000)
    decoded: dict[tuple[int, str], list] = {}
    for f in decode(out / "lm-topo50.img"):
        p = f["properties"]
        if p["kind"] == "polygon":
            geom = shapely.transform(shape(f["geometry"]), project.transform, interleaved=False)
            decoded.setdefault((p["level"], p["type"]), []).append(geom)
    for level in range(6):
        polygons = decoded[level, "0x50"]
        assert any(g.covers(west_point) for g in polygons)
        assert any(g.covers(east_point) for g in polygons)
        assert any(g.covers(west_point) and g.covers(east_point) for g in polygons) == (level == 4)
        assert all(
            not g.covers(hole) for g in polygons for hole in (lake.centroid, clearing.centroid)
        )
    assert any(g.covers(lake.centroid) for g in decoded[4, "0x3c"])
    assert any(g.covers(clearing.centroid) for g in decoded[4, "0x10f03"])
