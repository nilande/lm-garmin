"""Verify replacement levels and the original labels in compiled maps."""

from collections import defaultdict

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


def write_layer(path, layer, geometry, **columns):
    pyogrio.write_arrow(
        pa.table({"geom": [geometry.wkb], **{key: [value] for key, value in columns.items()}}),
        path,
        layer=layer,
        geometry_name="geom",
        geometry_type=geometry.geom_type,
        crs="EPSG:3006",
    )


@pytest.mark.parametrize("scales", [(100,), (250,), (100, 250)])
def test_official_polygons_replace_only_the_selected_levels(tmp_path, scales):
    if not tools.find_java():
        pytest.skip("java not found")
    region = Region("official-overview", (505000, 7270000, 530000, 7290000))
    centers = {50: 510000, 100: 517000, 250: 524000}
    folders = {scale: tmp_path / str(scale) for scale in centers}
    for scale, folder in folders.items():
        folder.mkdir()
        x = centers[scale]
        path = folder / "mark_sverige.gpkg"
        write_layer(path, "mark", box(x - 1300, 7278700, x + 1300, 7281300), objekttypnr=2632)
        if scale != 50:
            code = 2651 if scale == 100 else 2653
            write_layer(path, "sankmark", box(x - 700, 7282000, x + 700, 7283400), objekttypnr=code)
    write_layer(
        folders[50] / "names.gpkg",
        "textpunkt",
        Point(510000, 7285000),
        textstrang="Topografi 50 town",
        textkategori="Tätort",
        textstorleksklass="8",
    )
    out = tmp_path / "out"
    build(
        folders[50],
        region,
        out,
        tmp_path / "cache",
        products=["topo50"],
        jobs=1,
        java_mem="1g",
        topo100_dir=folders[100] if 100 in scales else None,
        topo250_dir=folders[250] if 250 in scales else None,
    )
    projection = Transformer.from_crs(3006, 4326, always_xy=True)
    water = {scale: Point(projection.transform(x, 7280000)) for scale, x in centers.items()}
    wetland = {scale: Point(projection.transform(x, 7282700)) for scale, x in centers.items()}
    levels = defaultdict(set)
    named = defaultdict(list)
    for feature in decode(out / "lm-topo50.img"):
        p = feature["properties"]
        if p["kind"] == "point" and p.get("label"):
            named[p["level"]].append(p["label"])
        if p["kind"] != "polygon":
            continue
        for kind, probes in (("0x3c", water), ("0x51", wetland)):
            if p["type"] != kind:
                continue
            geometry = shape(feature["geometry"])
            for scale, point in probes.items():
                if geometry.covers(point):
                    levels[scale, kind].add(p["level"])
    replaced = {4 if scale == 100 else 5 for scale in scales}
    assert levels[50, "0x3c"] == set(range(6)) - replaced
    for scale, level in ((100, 4), (250, 5)):
        expected = {level} if scale in scales else set()
        assert levels[scale, "0x3c"] == levels[scale, "0x51"] == expected
    assert named == {level: ["Topografi 50 town"] for level in range(7)}
