from zipfile import ZipFile

import osmium
import pyarrow as pa
import pyogrio
import pytest
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, box

from lm_garmin import cli
from lm_garmin.administrative import named_regions

X, Y = 500_000, 7_300_000


def coords(*points):
    return [(X + x, Y + y) for x, y in points]


def write_layer(path, layer, geometries, geometry_type, **columns):
    pyogrio.write_arrow(
        pa.table({"geom": [geom.wkb for geom in geometries], **columns}),
        path,
        layer=layer,
        geometry_name="geom",
        geometry_type=geometry_type,
        crs="EPSG:3006",
    )


@pytest.fixture
def boundary_fixture(tmp_path):
    index = tmp_path / "scb.zip"
    with ZipFile(index, "w") as bundle:
        for name, prefix, codes, names, geometries in (
            ("LanSweref99TM", "Ln", ["23"], ["Jämtlands"], [box(X, Y, X + 480, Y + 1000)]),
            (
                "Kommun_Sweref99TM",
                "Kn",
                ["2301", "2302", "2303"],
                ["Västra", "Östra", "Saknad"],
                [
                    box(X, Y, X + 480, Y + 1000),
                    box(X + 500, Y, X + 1000, Y + 500),
                    box(X + 750, Y + 700, X + 900, Y + 850),
                ],
            ),
        ):
            shape = tmp_path / f"{name}.shp"
            write_layer(
                shape,
                name,
                geometries,
                "Polygon",
                **{f"{prefix}Kod": codes, f"{prefix}Namn": names},
            )
            zipped = tmp_path / f"{name}.zip"
            with ZipFile(zipped, "w") as member:
                for path in sorted(tmp_path.glob(f"{name}.*")):
                    if path != zipped:
                        member.write(path, path.name)
            bundle.write(zipped, zipped.name)

    gpkg_dir = tmp_path / "gpkg"
    gpkg_dir.mkdir()
    outline = coords((0, 0), (1000, 0), (1000, 500), (500, 500), (500, 1000), (0, 1000), (0, 0))
    lines = [LineString([a, b]) for a, b in zip(outline, outline[1:], strict=False)]
    lines.append(LineString(coords((500, 0), (500, 500))))
    write_layer(
        gpkg_dir / "administrativindelning_sverige.gpkg",
        "administrativ_grans",
        lines,
        "LineString",
        objekttypnr=[1563] * (len(lines) - 1) + [1564],
    )
    return index, gpkg_dir, Polygon(outline)


def test_names_codes_exact_polygon_and_fallback(boundary_fixture):
    index, gpkg_dir, outline = boundary_fixture
    (county,) = named_regions("county", [" JÄMTLANDS län ", "23"], gpkg_dir, index)
    assert county.id == "county-23"
    assert county.geometry.equals(outline)
    assert county.boundary_source == "Topografi 50"

    west, east, missing = named_regions(
        "municipality", ["Västra", "2302", "Saknad"], gpkg_dir, index
    )
    assert west.geometry.equals(box(X, Y, X + 500, Y + 1000))
    assert east.geometry.equals(box(X + 500, Y, X + 1000, Y + 500))
    assert missing.geometry.equals(box(X + 750, Y + 700, X + 900, Y + 850))
    assert missing.boundary_source == "SCB simplified boundary"
    with pytest.raises(ValueError, match="Unknown municipality"):
        named_regions("municipality", ["okänd"], gpkg_dir, index)


def test_convert_filters_outside_polygon_and_keeps_crossing_ways(boundary_fixture, tmp_path):
    index, gpkg_dir, _ = boundary_fixture
    src = gpkg_dir / "features.gpkg"
    write_layer(
        src,
        "textpunkt",
        [Point(p) for p in coords((700, 200), (800, 800))],
        "Point",
        textstrang=["inside", "outside"],
    )
    write_layer(
        src,
        "ovrig_vag",
        [LineString(coords((-50, 150), (1050, 150))), LineString(coords((700, 800), (900, 800)))],
        "LineString",
        objekttypnr=[1848, 1847],
    )
    out = tmp_path / "out"
    assert (
        cli.main(
            [
                "convert",
                "--county",
                "Jämtlands län",
                "--admin-index",
                str(index),
                "--gpkg-dir",
                str(gpkg_dir),
                "--out",
                str(out),
                "--jobs",
                "1",
            ]
        )
        == 0
    )
    names = [obj.tags["name"] for obj in osmium.FileProcessor(out / "text.osm.pbf")]
    assert names == ["inside"]
    tags = [
        obj.tags["lm:t"]
        for obj in osmium.FileProcessor(out / "kommunikation.osm.pbf")
        if obj.is_way()
    ]
    assert tags == ["1848"]
    transformer = Transformer.from_crs(4326, 3006, always_xy=True)
    eastings = [
        transformer.transform(obj.location.lon, obj.location.lat)[0]
        for obj in osmium.FileProcessor(out / "kommunikation.osm.pbf")
        if obj.is_node()
    ]
    assert min(eastings) < X < X + 1000 < max(eastings)
