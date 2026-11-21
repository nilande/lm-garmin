"""Street names from the NVDB fixture appear on decoded roads of the built map (issue #60)."""

from collections import Counter
from pathlib import Path

import pyogrio
import pytest

from lm_garmin import tools
from lm_garmin.build import build
from lm_garmin.products import PRODUCTS
from lm_garmin.region import sweden
from lm_garmin.verify import decode

pytestmark = pytest.mark.integration

DATA = Path(__file__).parents[1] / "data"
FX = "tatort_659_67_00"
ROAD_TYPES = {"0x4", "0x6"}  # 1809 Huvudgata, 1810/1811 Lokalgata


@pytest.fixture(scope="module")
def named_build(tmp_path_factory):
    if not tools.find_java():
        pytest.skip("java not found")
    src = tmp_path_factory.mktemp("src")
    (src / f"{FX}.gpkg").symlink_to(DATA / f"{FX}.gpkg")
    out = tmp_path_factory.mktemp("out")
    report = build(
        src,
        sweden(src),
        out,
        tmp_path_factory.mktemp("cache"),
        products=["topo50"],
        jobs=2,
        java_mem="1g",
        log=lambda *_: None,
        nvdb_dir=DATA / "nvdb",
    )
    return out, report


def test_street_names_on_decoded_roads(named_build):
    out, report = named_build
    _, _, _, fields = pyogrio.raw.read(
        DATA / "nvdb" / f"{FX}.nvdb.gpkg",
        layer="NVDB_DK_O_20_Gatunamn",
        columns=["Namn"],
        read_geometry=False,
    )
    nvdb_names = {n for n in fields[0] if n}
    labels: Counter[str] = Counter()
    roads = 0
    for f in decode(out / PRODUCTS["topo50"].filename):
        p = f["properties"]
        if p["kind"] == "line" and p["level"] == 0 and p["type"] in ROAD_TYPES:
            roads += 1
            if p["label"]:
                labels[p["label"]] += 1
    assert roads
    assert sum(labels.values()) / roads > 0.8
    # Labels on town streets are NVDB names (or road numbers on main streets).
    assert sum(n for name, n in labels.items() if name in nvdb_names) / sum(labels.values()) > 0.95
    assert len(labels) > 50


def test_report_and_copyright(named_build):
    out, report = named_build
    convert = next(s for s in report["steps"] if s["name"].startswith("convert"))
    sn = convert["detail"]["street_names"]
    assert sn["named_share_by_class"]["1811"] > 0.9
    assert report["nvdb_sources"]
    img = (out / PRODUCTS["topo50"].filename).read_bytes()
    assert b"Trafikverket (NVDB)" in img
