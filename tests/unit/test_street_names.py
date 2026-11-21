"""Street-name matching against NVDB name lines (issue #60), on synthetic geometry."""

from pathlib import Path

import numpy as np
import pyogrio
import pytest
import shapely
from shapely.geometry import LineString

from lm_garmin import street_names
from lm_garmin.street_names import NameIndex, Params, _union, assign

DATA = Path(__file__).parents[1] / "data"


def index(*lines: tuple[str, list[tuple[float, float]]], params: Params = street_names.PARAMS):
    geoms = np.array([LineString(c) for _, c in lines], dtype=object)
    return NameIndex(geoms, [n for n, _ in lines], params)


def names(m):
    return [(round(g.length), n) for g, n in m.pieces]


def test_parallel_line_names_the_whole_segment():
    road = LineString([(0, 0), (200, 0)])
    m = index(("Storgatan", [(-10, 5), (210, 5)])).match(road)
    assert names(m) == [(200, "Storgatan")]
    assert not m.ambiguous


def test_crossing_street_is_ignored():
    road = LineString([(0, 0), (200, 0)])
    m = index(("Tvärgatan", [(100, -100), (100, 100)])).match(road)
    assert names(m) == [(200, None)]


def test_far_line_is_ignored():
    road = LineString([(0, 0), (200, 0)])
    m = index(("Långt bort", [(0, 40), (200, 40)])).match(road)
    assert names(m) == [(200, None)]


def test_overlapping_lines_of_one_name_are_unioned():
    """Two NVDB lines of the same name over the same 80 m must not count as 160 m."""
    road = LineString([(0, 0), (200, 0)])
    idx = index(("Kortgatan", [(0, 3), (80, 3)]), ("Kortgatan", [(0, -3), (80, -3)]))
    cover = idx.cover(road)
    assert pytest.approx(sum(b - a for a, b in cover["Kortgatan"]), abs=0.5) == 80
    # 40 % covered → below min_share, so only the covered stretch is named.
    assert names(idx.match(road)) == [(80, "Kortgatan"), (120, None)]


def test_segment_is_split_where_the_name_changes():
    road = LineString([(0, 0), (300, 0)])
    idx = index(("Norra vägen", [(0, 4), (180, 4)]), ("Södra vägen", [(180, 4), (300, 4)]))
    m = idx.match(road)
    assert names(m) == [(180, "Norra vägen"), (120, "Södra vägen")]
    assert m.split
    assert shapely.equals_exact(m.pieces[0][0].boundary.geoms[1], m.pieces[1][0].boundary.geoms[0])


def test_short_stretches_merge_into_a_neighbour():
    """A 10 m stretch of another name at a junction does not become its own piece."""
    road = LineString([(0, 0), (200, 0)])
    idx = index(("Huvudgatan", [(10, 2), (200, 2)]), ("Sidogatan", [(0, 2), (10, 2)]))
    assert names(idx.match(road)) == [(200, "Huvudgatan")]


def test_mostly_covered_segment_is_named_whole():
    road = LineString([(0, 0), (200, 0)])
    idx = index(("Ågatan", [(0, 2), (130, 2)]))
    assert names(idx.match(road)) == [(200, "Ågatan")]


def test_two_names_on_the_same_stretch_are_ambiguous():
    road = LineString([(0, 0), (200, 0)])
    idx = index(("Gamla vägen", [(0, 3), (200, 3)]), ("Nya vägen", [(0, -3), (120, -3)]))
    m = idx.match(road)
    assert m.ambiguous
    assert names(m) == [(200, "Gamla vägen")]  # the larger cover wins


def test_curved_road_uses_local_bearing():
    """An L-shaped road: each leg is matched by its own direction."""
    road = LineString([(0, 0), (200, 0), (200, 200)])
    idx = index(("Östra gatan", [(0, 3), (197, 3)]), ("Norra gatan", [(197, 3), (197, 200)]))
    m = idx.match(road)
    assert [n for _, n in m.pieces] == ["Östra gatan", "Norra gatan"]
    assert [g.length for g, _ in m.pieces] == pytest.approx([200, 200], abs=5)


def test_assign_without_cover_and_zero_length():
    road = LineString([(0, 0), (100, 0)])
    assert names(assign(road, {})) == [(100, None)]
    assert _union([(5, 10), (0, 6), (20, 30)]) == [(0, 10), (20, 30)]


def test_stats():
    s = street_names.MatchStats()
    road = LineString([(0, 0), (100, 0)])
    s.add("1811", 100, 80, street_names.Match([(road, "x")]))
    s.add("1811", 100, 0, street_names.Match([(road, None)]))
    d = s.as_dict()
    assert d["segments"] == 2
    assert d["named_share"] == 0.4
    assert d["named_share_by_class"] == {"1811": 0.4}


def test_fixture_reads_and_names_roads():
    """The CC0 NVDB cut-out names most town streets of the tatort fixture."""
    nvdb = street_names.sources(DATA / "nvdb")
    bbox = (670000, 6590000, 675000, 6595000)
    idx = NameIndex.read(nvdb, bbox)
    assert len(idx) > 1000
    _, _, wkb, fields = pyogrio.raw.read(
        DATA / "tatort_659_67_00.gpkg", layer="vaglinje", columns=["objekttypnr"]
    )
    total = named = 0.0
    for geom, t in zip(shapely.from_wkb(wkb), fields[0], strict=True):
        if int(t) not in (1809, 1810, 1811):
            continue
        for line in shapely.get_parts(geom):
            m = idx.match(line)
            total += line.length
            named += sum(g.length for g, n in m.pieces if n)
    assert named / total >= 0.9


def test_sources_rejects_folders_without_nvdb(tmp_path):
    with pytest.raises(FileNotFoundError):
        street_names.sources(tmp_path)
    (tmp_path / "x.gpkg").symlink_to(DATA / "tatort_659_67_00.gpkg")
    with pytest.raises(ValueError, match="NVDB"):
        street_names.sources(tmp_path)
