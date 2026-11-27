"""Junctions of the routable network (#28)."""

import numpy as np
import osmium
import shapely

from lm_garmin import network
from lm_garmin.convert import OsmSink


def line(*xy):
    return shapely.LineString(xy)


def test_a_path_crossing_a_road_at_level_gets_a_shared_vertex_on_both():
    road = line((0, 0), (100, 0))
    path = line((50, -50), (50, 50))
    j = network.Junctions.of([("vaglinje", 1, road, True), ("ovrig_vag", 2, path, True)])
    assert list(j.apply("vaglinje", 1, road).coords) == [(0, 0), (50, 0), (100, 0)]
    assert (50, 0) in list(j.apply("ovrig_vag", 2, path).coords)
    assert j.shared(network.key([(50, 0)]))[0] >= 0
    assert j.stats()["inserted"] == 1


def test_no_junction_where_a_road_is_a_bridge():
    road = line((0, 0), (100, 0))
    path = line((50, -50), (50, 50))
    j = network.Junctions.of([("vaglinje", 1, road, False), ("ovrig_vag", 2, path, True)])
    assert j.apply("vaglinje", 1, road) is road
    assert j.shared(network.key([(50, 0)]))[0] == -1


def test_a_path_ending_on_a_road_joins_it_even_at_a_bridge():
    road = line((0, 0), (100, 0))
    path = line((40, 30), (40, 0))  # T-junction: the path ends on the road
    j = network.Junctions.of([("vaglinje", 1, road, False), ("ovrig_vag", 2, path, True)])
    assert list(j.apply("vaglinje", 1, road).coords) == [(0, 0), (40, 0), (100, 0)]
    assert j.shared(network.key([(40, 0)]))[0] >= 0


def test_a_loose_end_within_a_metre_is_moved_onto_the_line():
    road = line((0, 0), (100, 0))
    near = line((20, 30), (20, 0.6))
    far = line((80, 30), (80, 2.0))
    j = network.Junctions.of(
        [("vaglinje", 1, road, True), ("ovrig_vag", 2, near, True), ("ovrig_vag", 3, far, True)]
    )
    assert list(j.apply("ovrig_vag", 2, near).coords)[-1] == (20, 0)
    assert (20, 0) in list(j.apply("vaglinje", 1, road).coords)
    assert j.apply("ovrig_vag", 3, far) is far
    assert j.stats()["snapped"] == 1


def test_existing_shared_vertices_become_shared_nodes():
    a = line((0, 0), (10, 0))
    b = line((10, 0), (20, 5))
    j = network.Junctions.of([("vaglinje", 1, a, True), ("vaglinje", 2, b, True)])
    assert j.stats()["inserted"] == 0
    assert np.array_equal(j.shared(network.key([(10, 0), (0, 0)])) >= 0, [True, False])


def test_winter_trails_are_not_routable():
    assert network.routable("ovrig_vag", 1846)
    assert not network.routable("ovrig_vag", 1848)
    assert not network.routable("hydrolinje", 1)


def test_key_round_trips_on_a_centimetre_grid():
    xy = np.array([[674012.345, 6594001.239], [200000.0, 7680000.0]])
    assert np.allclose(network.unkey(network.key(xy)), np.round(xy, 2))


def test_sink_writes_shared_nodes_once_and_joins_split_pieces(tmp_path):
    out = tmp_path / "t.osm.pbf"
    sink = OsmSink(out, 1000, (0, 0, 1, 1), shared=np.array([[0.5, 0.5]]))
    sink.way(np.array([[0.1, 0.1], [0.5, 0.5]]), {"a": "1"}, shared=np.array([-1, 0]))
    sink.way(np.array([[0.5, 0.5], [0.9, 0.1]]), {"a": "2"}, shared=np.array([0, -1]))
    end = sink.last_node
    sink.way(np.array([[0.9, 0.1], [0.9, 0.9]]), {"a": "3"}, shared=np.array([-1, -1]), first=end)
    ring = np.array([[0.2, 0.2], [0.3, 0.2], [0.2, 0.3], [0.2, 0.2]])
    sink.way(ring, {"a": "4"}, shared=np.array([-1, -1, -1, -1]))
    sink.close()
    ways = {
        w.tags["a"]: [n.ref for n in w.nodes] for w in osmium.FileProcessor(str(out)) if w.is_way()
    }
    assert ways["1"][1] == ways["2"][0] == 1000  # the shared node, written first
    assert ways["3"][0] == ways["2"][1]
    assert ways["4"][0] == ways["4"][-1]
    nodes = [n.id for n in osmium.FileProcessor(str(out)) if n.is_node()]
    assert nodes == sorted(nodes) and len(nodes) == len(set(nodes)) == 7
