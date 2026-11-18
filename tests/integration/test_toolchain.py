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


@pytest.mark.skip(reason="M1: build fixtures to .img, decode and check object types")
def test_build_fixtures_to_img(): ...


@pytest.mark.skip(reason="M3: snowmobile completeness gate on the decoded overlay")
def test_snowmobile_completeness(): ...
