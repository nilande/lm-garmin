"""Build the optional overlay from synthetic OSM and Lantmäteriet geometry."""

import pyarrow as pa
import pyogrio
import pytest
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, shape

from lm_garmin import tools
from lm_garmin.build import build
from lm_garmin.convert import OsmSink
from lm_garmin.region import Region
from lm_garmin.verify import decode

pytestmark = pytest.mark.integration


def test_osm_overlay_is_opt_in_and_keeps_unmatched_sections(tmp_path):
    if not tools.find_java():
        pytest.skip("java not found")
    region = Region("test", (515000, 7270000, 520000, 7275000))
    src = tmp_path / "src"
    src.mkdir()
    lm = LineString([(516000, 7272000), (516600, 7272000)])
    pyogrio.write_arrow(
        pa.table({"geom": [lm.wkb], "objekttypnr": [1848], "skoterkorning_tillaten": ["Nej"]}),
        src / "lm.gpkg",
        layer="ovrig_vag",
        geometry_name="geom",
        geometry_type="LineString",
        crs="EPSG:3006",
    )
    osm = tmp_path / "test.osm.pbf"
    project = Transformer.from_crs(3006, 4326, always_xy=True)
    sink = OsmSink(osm, 1, project.transform_bounds(*region.bbox))
    for name, coords, tags in (
        ("Duplicate", [(516000, 7272010), (516550, 7272010)], {"snowmobile": "yes"}),
        ("Extension", [(516000, 7272010), (516900, 7272010)], {"snowmobile": "designated"}),
        ("Crossing", [(516400, 7271800), (516400, 7272300)], {"snowmobile": "yes"}),
        ("Ice", [(516050, 7272600), (516450, 7272600)], {"snowmobile": "yes", "ice_road": "yes"}),
        ("Closed", [(516050, 7272800), (516450, 7272800)], {"snowmobile": "no"}),
    ):
        geom = shapely.transform(LineString(coords), project.transform, interleaved=False)
        sink.way(shapely.get_coordinates(geom), {**tags, "name": name})
    sink.close()

    out = tmp_path / "out"
    report = build(src, region, out, tmp_path / "cache", jobs=1, java_mem="1g", osm=osm, dev=True)
    assert set(report["outputs"]) == {"topo50", "skoter", "skoter-osm"}
    assert report["outputs"]["skoter-osm"]["family_id"] == 5756
    features = {
        f["properties"]["label"]: f
        for f in decode(out / "osm-dev-skoter.img")
        if f["properties"]["level"] == 0
    }
    assert {name: f["properties"]["type"] for name, f in features.items()} == {
        "Extension": "0x10c00",
        "Crossing": "0x10c01",
        "Ice": "0x10c02",
    }
    project = Transformer.from_crs(4326, 3006, always_xy=True)
    for name, expected_length in (("Extension", 261), ("Crossing", 500), ("Ice", 400)):
        line = shapely.transform(
            shape(features[name]["geometry"]), project.transform, interleaved=False
        )
        assert line.length == pytest.approx(expected_length, abs=4)
