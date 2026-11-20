"""Compare the firm-wetland size rule with detail and wet-wetland styling."""

import pyarrow as pa
import pyogrio
import pytest
from pyproj import Transformer
from shapely.geometry import Point, box, shape

from lm_garmin import tools
from lm_garmin.build import build
from lm_garmin.region import Region
from lm_garmin.verify import decode

pytestmark = pytest.mark.integration


def test_small_firm_wetland_is_visible_only_on_detail_levels(tmp_path):
    if not tools.find_java():
        pytest.skip("java not found")
    src = tmp_path / "src"
    src.mkdir()
    small_firm = box(516000, 7271000, 516070, 7271110)
    large_firm = box(517000, 7271000, 517200, 7271170)
    wet = box(518000, 7271000, 518200, 7271170)
    pyogrio.write_arrow(
        pa.table(
            {
                "geom": [g.wkb for g in (small_firm, large_firm, wet)],
                "objekttypnr": [2651, 2651, 2652],
            }
        ),
        src / "wetlands.gpkg",
        layer="sankmark",
        geometry_name="geom",
        geometry_type="Polygon",
        crs="EPSG:3006",
    )
    region = Region("wetland-test", (515000, 7270000, 520000, 7275000))
    out = tmp_path / "out"
    build(src, region, out, tmp_path / "cache", products=["topo50"], jobs=1, java_mem="1g")
    project = Transformer.from_crs(3006, 4326, always_xy=True)
    features = [
        (f["properties"], shape(f["geometry"]))
        for f in decode(out / "lm-topo50.img")
        if f["properties"]["kind"] == "polygon"
    ]
    for source, kind, expected in (
        (small_firm, "0x51", {0, 1, 2, 3}),
        (large_firm, "0x51", {0, 1, 2, 3, 4}),
        (wet, "0x10f04", {0, 1, 2, 3, 4}),
    ):
        c = source.centroid
        point = Point(project.transform(c.x, c.y))
        levels = {p["level"] for p, g in features if p["type"] == kind and g.covers(point)}
        assert levels == expected
