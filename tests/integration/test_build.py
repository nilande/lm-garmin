"""Build every fixture to .img, decode the result and check it (issues #7, #9, #10).

Only reports and timings leave the test – never map data.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from lm_garmin import stylegen, tools
from lm_garmin.build import build
from lm_garmin.products import PRODUCTS
from lm_garmin.region import sweden
from lm_garmin.verify import check, norm_type, summarize

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[2]
FIXTURES = ["fjall_727_51_05", "tatort_659_67_00", "skoter_730_51"]
REPORTS = ROOT / "reports"


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


def test_skoter_overlay_has_all_statuses(built):
    out, report = built["skoter_730_51"]
    s = summarize(out / PRODUCTS["skoter"].filename)
    assert s.types("line") == {norm_type(t) for t in ("0x10e10", "0x10e11", "0x10e12", "0x10e13")}
    assert s.counts[("point", norm_type("0x11610"))] == 3
    assert report["outputs"]["skoter"]["family_id"] == PRODUCTS["skoter"].family_id


def test_overlay_skipped_without_winter_trails(built):
    _, report = built["tatort_659_67_00"]
    assert "skoter" not in report["outputs"]


def test_build_reports_steps(built):
    for _, report in built.values():
        names = [s["name"] for s in report["steps"]]
        assert names[0] == "convert" and "compile:topo50" in names
        assert all(s["seconds"] >= 0 for s in report["steps"])
