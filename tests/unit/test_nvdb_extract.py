"""`lm-garmin nvdb extract`: keep only the NVDB name layers (issue #60)."""

import json
import zipfile
from pathlib import Path

import pyogrio
import pytest

from lm_garmin import street_names
from lm_garmin.cli import main
from lm_garmin.nvdb_extract import extract

FIXTURE = Path(__file__).parents[1] / "data" / "nvdb" / "tatort_659_67_00.nvdb.gpkg"


def county_zip(tmp_path: Path, name: str) -> Path:
    z = tmp_path / f"{name}_geopackage.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(FIXTURE, f"{name}/nvdb_{name}.gpkg")
    return z


def test_extract_from_zips_and_gpkg(tmp_path):
    zips = [county_zip(tmp_path, "a"), county_zip(tmp_path, "b")]
    out = tmp_path / "nvdb" / "nvdb-names.gpkg"
    sources = extract([*zips, FIXTURE], out, log=lambda *_: None)
    assert [s.file for s in sources] == ["a_geopackage.zip", "b_geopackage.zip", FIXTURE.name]
    n = pyogrio.read_info(FIXTURE, layer=street_names.GATUNAMN)["features"]
    assert pyogrio.read_info(out, layer=street_names.GATUNAMN)["features"] == 3 * n
    assert pyogrio.read_info(out, layer=street_names.GATUNAMN)["fields"].tolist() == ["Namn"]
    assert street_names.sources(out.parent) == [out]
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert len(meta["sources"]) == 3 and all(len(s["sha256"]) == 64 for s in meta["sources"])
    # Counties overlap at their borders: the index reads each line once.
    index = street_names.NameIndex.read([out], (670000, 6590000, 675000, 6595000))
    single = street_names.NameIndex.read([FIXTURE], (670000, 6590000, 675000, 6595000))
    assert len(index) == len(single)


def test_rejects_non_nvdb_files(tmp_path):
    other = Path(__file__).parents[1] / "data" / "tatort_659_67_00.gpkg"
    with pytest.raises(ValueError, match="NVDB"):
        extract([other], tmp_path / "out.gpkg", log=lambda *_: None)
    assert not (tmp_path / "out.gpkg").exists()


def test_cli(tmp_path, capsys):
    folder = tmp_path / "zips"
    folder.mkdir()
    county_zip(folder, "c")
    out = tmp_path / "names" / "nvdb-names.gpkg"
    assert main(["nvdb", "extract", str(folder), "--out", str(out)]) == 0
    assert "name lines from 1 files" in capsys.readouterr().out
