"""Integration tests. The full fixture build arrives with milestone M1."""

import subprocess

import pytest

from lm_garmin import tools

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def java():
    j = tools.find_java()
    if not j:
        pytest.skip("java not found")
    return j


@pytest.mark.parametrize("name", ["mkgmap", "splitter"])
def test_pinned_tool_runs(java, name):
    jar = tools.fetch(tools.TOOLS[name])
    out = subprocess.run([java, "-jar", str(jar), "--version"], capture_output=True, text=True)
    assert tools.TOOLS[name].version.lstrip("r") in out.stdout + out.stderr


@pytest.mark.parametrize("fixture", ["fjall_727_51_05", "tatort_659_67_00", "skoter_730_51"])
def test_converted_fixture_is_accepted_by_splitter(java, fixture, data_dir, tmp_path):
    """All theme PBFs of a fixture go through splitter in one run (ids, ordering)."""
    from lm_garmin.convert import convert
    from lm_garmin.region import sweden

    src = tmp_path / "src"
    src.mkdir()
    (src / f"{fixture}.gpkg").symlink_to(data_dir / f"{fixture}.gpkg")
    pbf = tmp_path / "pbf"
    stats = convert(src, sweden(src), pbf, jobs=2, log=lambda *_: None)
    inputs = [str(pbf / s.pbf) for s in stats if s.features]
    jar = tools.fetch(tools.TOOLS["splitter"])
    out = subprocess.run(
        [java, "-jar", str(jar), f"--output-dir={tmp_path / 'split'}", "--mapid=57300001", *inputs],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]
    assert list((tmp_path / "split").glob("*.osm.pbf"))


@pytest.mark.skip(reason="M1 (#7, #10): build fixtures to .img, decode and check object types")
def test_build_fixtures_to_img(): ...


@pytest.mark.skip(reason="M3: snowmobile completeness gate on the decoded overlay")
def test_snowmobile_completeness(): ...
