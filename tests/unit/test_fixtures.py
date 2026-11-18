"""The committed test data must stay small, complete and well-formed."""

import sqlite3
from pathlib import Path

import pytest

DATA = Path(__file__).parents[1] / "data"
FIXTURES = ["fjall_727_51_05", "tatort_659_67_00", "skoter_730_51"]
MAX_BYTES = 5_000_000


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_exists_and_is_small(name):
    p = DATA / f"{name}.gpkg"
    assert p.exists(), f"missing {p}; run scripts/make_fixtures.py"
    assert p.stat().st_size < MAX_BYTES


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_has_all_44_layers_in_sweref(name):
    with sqlite3.connect(DATA / f"{name}.gpkg") as c:
        rows = c.execute("SELECT table_name, srs_id FROM gpkg_contents").fetchall()
    assert len(rows) == 44
    assert {srs for _, srs in rows} == {3006}


def test_skoter_fixture_covers_all_snowmobile_values():
    with sqlite3.connect(DATA / "skoter_730_51.gpkg") as c:
        combos = set(
            c.execute(
                "SELECT objekttypnr, skoterkorning_tillaten FROM ovrig_vag "
                "WHERE objekttypnr IN (1847, 1848)"
            ).fetchall()
        )
        n1836 = c.execute(
            "SELECT count(*) FROM ledintressepunkt_fjall WHERE objekttypnr = 1836"
        ).fetchone()[0]
    values = {"Ja", "Nej", "Påbjuden", "Ingen information"}
    assert combos == {(t, v) for t in (1847, 1848) for v in values}
    assert n1836 >= 1


def test_provenance_lists_every_fixture():
    text = (DATA / "PROVENANCE.md").read_text(encoding="utf-8")
    for name in FIXTURES:
        assert f"`{name}.gpkg`" in text


def test_ci_track_is_synthetic():
    head = (DATA / "tracks" / "ci_handmade.gpx").read_text(encoding="utf-8")[:400]
    assert "NOT Skoterleder.org" in head
