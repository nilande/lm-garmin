"""Guard rails: no map data outside tests/data, no large files."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
DATA_SUFFIXES = {".gpkg", ".img", ".tif", ".tiff", ".pbf", ".osm", ".o5m", ".gpx", ".zip"}


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [ROOT / f for f in out.splitlines()]


def test_map_data_only_in_tests_data():
    offenders = [
        p.relative_to(ROOT)
        for p in tracked_files()
        if p.suffix.lower() in DATA_SUFFIXES and "tests/data" not in p.as_posix()
    ]
    assert offenders == []


def test_no_large_files():
    big = [p.relative_to(ROOT) for p in tracked_files() if p.exists() and p.stat().st_size > 5e6]
    assert big == []
