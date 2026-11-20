"""Build every fixture to .img, decode the result and check it (issues #7, #9, #10).

Only reports and timings leave the test – never map data.
"""

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyogrio
import pytest
from numpy import ndarray
from pyproj import Transformer
from shapely import STRtree, from_wkb, get_parts, transform
from shapely.geometry import Point, Polygon, box, shape

from lm_garmin import stylegen, tools
from lm_garmin.build import build
from lm_garmin.coverage import measure
from lm_garmin.products import PRODUCTS
from lm_garmin.region import Region, sweden
from lm_garmin.render import run as render
from lm_garmin.verify import check, decode, norm_type, summarize

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[2]
FIXTURES = ["fjall_727_51_05", "tatort_659_67_00", "skoter_730_51"]
REPORTS = ROOT / "reports"
SKOTER_TYPES = {
    (1847, "Ja"): "0x10e10",
    (1847, "Påbjuden"): "0x10e11",
    (1847, "Nej"): "0x10e12",
    (1847, "Ingen information"): "0x10e13",
    (1848, "Ja"): "0x10e14",
    (1848, "Påbjuden"): "0x10e15",
    (1848, "Nej"): "0x10e16",
    (1848, "Ingen information"): "0x10e17",
}


def present_types(gpkg: Path) -> dict[tuple[str, str], int]:
    """(layer, objekttypnr or '') → feature count, for all non-empty layers."""
    out = {}
    with sqlite3.connect(gpkg) as c:
        for (layer,) in c.execute("SELECT table_name FROM gpkg_contents"):
            cols = {r[1] for r in c.execute(f'PRAGMA table_info("{layer}")')}
            if "objekttypnr" in cols:
                q = f'SELECT objekttypnr, count(*) FROM "{layer}" GROUP BY 1'
                for t, n in c.execute(q):
                    out[(layer, str(t))] = n
            else:
                n = c.execute(f'SELECT count(*) FROM "{layer}"').fetchone()[0]
                if n:
                    out[(layer, "")] = n
    return out


@pytest.fixture(scope="module")
def built(tmp_path_factory, data_dir_module):
    if not tools.find_java():
        pytest.skip("java not found")
    results = {}
    for fx in FIXTURES:
        src = tmp_path_factory.mktemp(f"src-{fx}")
        (src / f"{fx}.gpkg").symlink_to(data_dir_module / f"{fx}.gpkg")
        out = tmp_path_factory.mktemp(f"out-{fx}")
        report = build(
            src,
            sweden(src),
            out,
            tmp_path_factory.mktemp(f"cache-{fx}"),
            jobs=2,
            java_mem="1g",
            log=lambda *_: None,
        )
        REPORTS.mkdir(exist_ok=True)
        (REPORTS / f"build-{fx}.json").write_text(json.dumps(report, indent=1))
        results[fx] = (out, report)
    return results


@pytest.fixture(scope="module")
def data_dir_module():
    return ROOT / "tests" / "data"


@pytest.mark.parametrize("fx", FIXTURES)
def test_base_map_has_expected_types_and_labels(built, fx, data_dir_module):
    out, _ = built[fx]
    s = summarize(out / PRODUCTS["topo50"].filename)
    expect = json.loads((data_dir_module / "expect" / f"{fx}.json").read_text(encoding="utf-8"))
    assert check(s, expect) == []

    rules = stylegen.load(PRODUCTS["topo50"].style_dir / "mapping.csv")
    decoded = s.types()
    missing = []
    for (layer, t), n in present_types(data_dir_module / f"{fx}.gpkg").items():
        cands = [r for r in rules if r.layer == layer and r.t in (t, "")]
        if any(r.kind == "drop" for r in cands):
            continue
        if not {norm_type(r.type) for r in cands} & decoded:
            missing.append(f"{layer}/{t or '*'} ({n} features) → {sorted({r.type for r in cands})}")
    assert missing == []


def assert_points_match(source: ndarray, decoded: list[Point]) -> None:
    assert len(decoded) == len(source), f"1836 point count: {len(decoded)} != {len(source)}"
    spatial_index = STRtree(decoded)
    candidates = [
        [
            int(i)
            for i in spatial_index.query(point, predicate="dwithin", distance=5)
            if point.distance(decoded[i]) < 5
        ]
        for point in source
    ]
    matches: dict[int, int] = {}

    def assign(source_index: int, visited: set[int]) -> bool:
        for decoded_index in candidates[source_index]:
            if decoded_index in visited:
                continue
            visited.add(decoded_index)
            previous = matches.get(decoded_index)
            if previous is None or assign(previous, visited):
                matches[decoded_index] = source_index
                return True
        return False

    for source_index in range(len(source)):
        assert assign(source_index, set()), (
            f"No distinct decoded 1836 point within 5 m of source point {source_index + 1}"
        )


@pytest.mark.parametrize("fx", ["fjall_727_51_05", "skoter_730_51"])
def test_snowmobile_completeness(built, fx, data_dir_module):
    out, report = built[fx]
    gpkg = data_dir_module / f"{fx}.gpkg"
    meta, trails = pyogrio.read_arrow(
        gpkg,
        layer="ovrig_vag",
        columns=["objekttypnr", "skoterkorning_tillaten"],
        where="objekttypnr IN (1847, 1848)",
    )
    source_lengths: Counter[tuple[int, str]] = Counter()
    for row in trails.to_pylist():
        key = row["objekttypnr"], row["skoterkorning_tillaten"] or "Ingen information"
        source_lengths[key] += from_wkb(row[meta["geometry_name"]]).length
    assert source_lengths
    if fx == "skoter_730_51":
        assert source_lengths.keys() == SKOTER_TYPES.keys()

    meta, points = pyogrio.read_arrow(
        gpkg, layer="ledintressepunkt_fjall", columns=[], where="objekttypnr = 1836"
    )
    source_points = get_parts(from_wkb(points[meta["geometry_name"]].to_pylist()))
    if fx == "skoter_730_51":
        assert len(source_points) == 3

    project = Transformer.from_crs(4326, 3006, always_xy=True)
    decoded_lengths: Counter[str] = Counter()
    decoded_points = []
    for feature in decode(out / PRODUCTS["skoter"].filename):
        props = feature["properties"]
        if props["level"] != 0:
            continue
        geometry = transform(shape(feature["geometry"]), project.transform, interleaved=False)
        if props["kind"] == "line":
            decoded_lengths[props["type"]] += geometry.length
        else:
            assert (props["kind"], props["type"]) == ("point", "0x11610")
            decoded_points.append(geometry)

    for key, garmin_type in SKOTER_TYPES.items():
        assert decoded_lengths.pop(garmin_type, 0) == pytest.approx(
            source_lengths[key], rel=0.01, abs=0
        ), f"{fx}: source trail {key} must be emitted as {garmin_type} within 1% of its length"
    assert not decoded_lengths, f"{fx}: unexpected winter trail types {list(decoded_lengths)}"
    assert_points_match(source_points, decoded_points)
    assert report["outputs"]["skoter"]["family_id"] == PRODUCTS["skoter"].family_id


def test_overlay_skipped_without_winter_trails(built):
    _, report = built["tatort_659_67_00"]
    assert "skoter" not in report["outputs"]


def test_synthetic_track_coverage(built, data_dir_module):
    out, _ = built["skoter_730_51"]
    gpx = data_dir_module / "tracks" / "ci_handmade.gpx"
    result = measure(out / PRODUCTS["skoter"].filename, gpx)
    print(result)
    assert result.track_m == pytest.approx(5233, abs=5)
    assert result.within_25m == pytest.approx(0.81, abs=0.01)
    assert result.within_50m == pytest.approx(0.82, abs=0.01)
    assert result.within_25m < result.within_50m


def test_build_reports_steps(built):
    for _, report in built.values():
        names = [s["name"] for s in report["steps"]]
        assert names[0].startswith("convert:") and "compile:topo50" in names
        assert all(s["seconds"] >= 0 for s in report["steps"])


@pytest.mark.parametrize("fixture", ["fjall_727_51_05", "tatort_659_67_00"])
def test_raster_comparison(built, data_dir_module, tmp_path, fixture):
    out, _ = built[fixture]
    report = render(
        out / PRODUCTS["topo50"].filename,
        tmp_path,
        reference=data_dir_module / f"{fixture}.ref50k.tif",
    )
    assert (report["width"], report["height"]) == (1000, 1000)
    assert report["reference_pixels"] == 1_000_000
    assert report["classified_pixels"] > 600_000
    assert report["classes"]["water"]["iou"] > 0.8
    for file in ("render.png", "side-by-side.png", "diff.png"):
        assert (tmp_path / file).stat().st_size > 0
    reports = REPORTS / "raster"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"{fixture}.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"{fixture}: "
        + ", ".join(
            f"{cls}={values['iou']:.1%}"
            for cls, values in report["classes"].items()
            if values["iou"] is not None
        )
    )


def test_contour_detail_and_labels_by_zoom_level(built, data_dir_module):
    out, _ = built["fjall_727_51_05"]
    labels: dict[tuple[int, str], set[str]] = defaultdict(set)
    index_counts: Counter[int] = Counter()
    for f in decode(out / PRODUCTS["topo50"].filename):
        p = f["properties"]
        if p["kind"] == "line" and p["type"] in {"0x20", "0x21", "0x22"}:
            labels[p["level"], p["type"]].add(p["label"])
            if p["type"] == "0x22":
                index_counts[p["level"]] += 1
    for level in (0, 1):
        assert labels[level, "0x20"] == {""}
        assert labels[level, "0x21"] <= {""}
    for level in (2, 3, 4):
        assert labels[level, "0x22"] == {""}
        assert not labels[level, "0x20"]
        assert not labels[level, "0x21"]
    assert 0 < index_counts[4] < index_counts[3]
    with sqlite3.connect(data_dir_module / "fjall_727_51_05.gpkg") as c:
        heights = {
            int(r[0])
            for r in c.execute("SELECT DISTINCT hojdvarde FROM hojdlinje WHERE stodkurva = 'Ja'")
        }
    expected_labels = {str(round(h * 3.28084)) for h in heights}
    assert labels[0, "0x22"] == expected_labels
    assert labels[1, "0x22"] and labels[1, "0x22"] <= expected_labels


def test_large_information_text_requires_detailed_zoom(built):
    out, _ = built["skoter_730_51"]
    levels = {
        p["level"]
        for f in decode(out / PRODUCTS["topo50"].filename)
        if (p := f["properties"])["kind"] == "point"
        and (p["label"] or "").startswith("Förbjudet område för terrängfordon")
    }
    assert levels == {0, 1}


def test_dev_build_of_two_regions_in_one_map(tmp_path, data_dir_module):
    """Two areas → one map with distinct tile numbers per area and dev family ids."""
    from lm_garmin.products import dev_variant

    src = tmp_path / "src"
    src.mkdir()
    for fx in ("fjall_727_51_05", "skoter_730_51"):
        (src / f"{fx}.gpkg").symlink_to(data_dir_module / f"{fx}.gpkg")
    regions = [
        Region("a", (515000, 7270000, 520000, 7275000)),
        Region("b", (510000, 7300000, 520000, 7310000)),
    ]
    out = tmp_path / "out"
    rep = build(
        src, regions, out, tmp_path / "cache", jobs=2, java_mem="1g", dev=True, log=lambda *_: None
    )
    topo = dev_variant(PRODUCTS["topo50"])
    assert rep["outputs"]["topo50"]["file"] == "lm-dev-topo50.img"
    assert rep["outputs"]["topo50"]["family_id"] == topo.family_id
    s = summarize(out / "lm-dev-topo50.img")
    assert s.tiles == {str(topo.mapid_base), str(topo.mapid_base + 1000)}
    assert {"Lövlund", "Syterstugan"} <= s.labels
    assert (out / "lm-dev-skoter.img").exists()


def test_restriction_area_draws_outer_and_inner_boundaries(tmp_path):
    if not tools.find_java():
        pytest.skip("java not found")
    outer = box(516000, 7271000, 519000, 7274000)
    inner = box(517000, 7272000, 518000, 7273000)
    area = Polygon(outer.exterior.coords, [inner.exterior.coords])
    src = tmp_path / "src"
    src.mkdir()
    pyogrio.write_arrow(
        pa.table({"geom": [area.wkb]}),
        src / "restriction.gpkg",
        layer="restriktionsomrade",
        geometry_name="geom",
        geometry_type="Polygon",
        crs="EPSG:3006",
    )
    region = Region("restriction", (515000, 7270000, 520000, 7275000))
    out = tmp_path / "out"
    build(src, region, out, tmp_path / "cache", jobs=1, java_mem="1g", log=lambda *_: None)

    boundaries = []
    for feature in decode(out / PRODUCTS["topo50"].filename):
        props = feature["properties"]
        assert props["type"] != "0x10f16"
        if props["type"] == "0x10d04" and props["kind"] == "line" and props["level"] == 0:
            boundaries.append(shape(feature["geometry"]))
    assert len(boundaries) == 2
    project = Transformer.from_crs(3006, 4326, always_xy=True)
    for x, y in ((516000, 7272500), (517000, 7272500)):
        point = Point(project.transform(x, y))
        assert min(line.distance(point) for line in boundaries) < 0.0001
