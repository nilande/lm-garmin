"""Opt-in budget check for the locally built 50 km Tärnaby reference map."""

import json
import os
from pathlib import Path

import pytest

from lm_garmin.verify import check, summarize

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMG = ROOT / "dist/tarnaby-overview/lm-dev-topo50.img"
BUDGET = ROOT / "docs/benchmarks/tarnaby-overview.json"


@pytest.mark.local_data
def test_tarnaby_overview_budget():
    img = Path(os.environ.get("LM_GARMIN_OVERVIEW_IMG", DEFAULT_IMG))
    if not img.is_file():
        pytest.skip("build the 50 km Tärnaby reference map first")
    problems = check(summarize(img), json.loads(BUDGET.read_text(encoding="utf-8")))
    assert not problems, "\n".join(problems)
