"""Round-trip a fixture through the converter and check the OSM output."""

import collections
import sqlite3

import osmium
import pytest

from lm_garmin.convert import ID_STRIDE, LAYER_THEME, THEMES, convert, id_base
from lm_garmin.region import Region

BBOX = (510000, 7300000, 520000, 7310000)


@pytest.fixture(scope="module")
def converted(tmp_path_factory, request):
    from pathlib import Path

    data = Path(request.config.rootpath) / "tests" / "data"
    src = tmp_path_factory.mktemp("src")
    (src / "skoter_730_51.gpkg").symlink_to(data / "skoter_730_51.gpkg")
    out = tmp_path_factory.mktemp("pbf")
    stats = convert(src, Region("t", BBOX), out, jobs=2, log=lambda *_: None)
    return data / "skoter_730_51.gpkg", out, {s.theme: s for s in stats}


class Obj:
    """Plain copy of an osmium object (osmium objects are only valid during iteration)."""

    def __init__(self, o):
        self.kind = o.type_str()
        self.id = o.id
        self.tags = dict(o.tags)
        self.lonlat = (o.location.lon, o.location.lat) if self.kind == "n" else None
        self.roles = [m.role for m in o.members] if self.kind == "r" else []

    def type_str(self):
        return self.kind


def objects(path):
    return [Obj(o) for o in osmium.FileProcessor(str(path))]


def test_every_layer_has_a_theme(data_dir):
    with sqlite3.connect(data_dir / "skoter_730_51.gpkg") as c:
        layers = {r[0] for r in c.execute("SELECT table_name FROM gpkg_contents")}
    assert layers == set(LAYER_THEME)


def test_feature_counts_match_source(converted):
    gpkg, _, stats = converted
    with sqlite3.connect(gpkg) as c:
        for theme in stats.values():
            for layer, n in theme.layers.items():
                assert n == c.execute(f'SELECT count(*) FROM "{layer}"').fetchone()[0], layer


def test_ids_ascending_in_theme_range_and_ordered(converted):
    _, out, stats = converted
    for theme in stats:
        lo, hi = id_base(theme), id_base(theme) + ID_STRIDE
        last = collections.defaultdict(int)
        kinds = []
        for o in objects(out / f"{theme}.osm.pbf"):
            k = o.type_str()
            assert lo <= o.id < hi
            assert o.id > last[k]
            last[k] = o.id
            if not kinds or kinds[-1] != k:
                kinds.append(k)
        assert kinds == sorted(kinds, key="nwr".index)


def test_snowmobile_tags(converted):
    _, out, _ = converted
    values = collections.Counter()
    for o in objects(out / "kommunikation.osm.pbf"):
        if o.type_str() == "w" and o.tags.get("lm:t") in ("1847", "1848"):
            values[(o.tags["lm:t"], o.tags.get("lm:skoterkorning_tillaten", "-"))] += 1
    # "Ingen information" is dropped: the style treats a missing tag as unknown.
    assert {v for _, v in values} == {"Ja", "Nej", "Påbjuden", "-"}
    assert {t for t, _ in values} == {"1847", "1848"}


def test_polygons_with_holes_become_multipolygons(converted):
    _, out, stats = converted
    rels = [o for o in objects(out / "mark.osm.pbf") if o.type_str() == "r"]
    assert len(rels) == stats["mark"].relations > 0
    for r in rels:
        roles = r.roles
        assert r.tags["type"] == "multipolygon" and roles[0] == "outer" and "inner" in roles


def test_coordinates_are_wgs84_in_region(converted):
    _, out, _ = converted
    for o in objects(out / "hojd.osm.pbf"):
        if o.type_str() == "n":
            lon, lat = o.lonlat
            assert 14.0 < lon < 16.0 and 65.5 < lat < 66.0


def test_theme_order_is_frozen():
    # Changing the order changes all OSM ids – append new themes at the end instead.
    assert THEMES[:3] == ["administrativindelning", "anlaggningsomrade", "byggnadsverk"]
    assert THEMES[-1] == "text"
