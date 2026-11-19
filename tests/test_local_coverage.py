"""Opt-in regression check against the private local GPX reference dataset."""

import os
from pathlib import Path

import pytest

from lm_garmin.coverage import gpx_files, measure

ROOT = Path(__file__).resolve().parents[1]
BASELINE_50M = 0.459
MAX_DROP = 0.01


@pytest.mark.local_data
def test_local_snowmobile_coverage():
    gpx = Path(
        os.environ.get("LM_GARMIN_COVERAGE_GPX", "/Volumes/scratch/lm-kartdata/snowmobile tracks")
    )
    if not gpx_files(gpx):
        pytest.skip("local GPX reference data unavailable")

    img = Path(os.environ.get("LM_GARMIN_COVERAGE_IMG", ROOT / "dist/coverage/lm-skoter.img"))
    assert img.is_file(), "Build the reference overlay or set LM_GARMIN_COVERAGE_IMG"

    result = measure(img, gpx)
    print(result)
    floor = BASELINE_50M - MAX_DROP
    assert result.within_50m >= floor, (
        f"50 m coverage dropped from the {BASELINE_50M:.1%} baseline to {result.within_50m:.1%} "
        f"(minimum {floor:.1%})"
    )
