"""`lm-garmin nvdb extract`: keep only the NVDB name layers (issue #60)."""

import json
import zipfile
from pathlib import Path

import pyogrio
import pytest
import shapely

from lm_garmin import street_names
from lm_garmin.cli import main
from lm_garmin.nvdb_extract import FILEGDB_LAYERS, extract

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


def county_filegdb_zip(tmp_path: Path, name: str) -> Path:
    """The FileGDB form of a county delivery: other layer and column names, MultiLineStrings."""
    gdb = tmp_path / f"{name}_FileGDB.gdb"
    meta, _, wkb, fields = pyogrio.raw.read(FIXTURE, layer=street_names.GATUNAMN, columns=["Namn"])
    multi = shapely.multilinestrings([[g] for g in shapely.from_wkb(wkb)])
    pyogrio.raw.write(
        gdb,
        geometry=shapely.to_wkb(multi),
        field_data=[fields[0]],
        fields=["Namn_130"],
        layer=FILEGDB_LAYERS[street_names.GATUNAMN],
        driver="OpenFileGDB",
        geometry_type="MultiLineString",
        crs="EPSG:3006",
    )
    z = tmp_path / f"{name}_filegdb.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in sorted(gdb.iterdir()):
            zf.write(f, f"{gdb.name}/{f.name}")
    return z


def test_extract_from_filegdb_zip(tmp_path):
    z = county_filegdb_zip(tmp_path, "d")
    out = tmp_path / "out" / "nvdb-names.gpkg"
    (s,) = extract([z], out, log=lambda *_: None)
    n = pyogrio.read_info(FIXTURE, layer=street_names.GATUNAMN)["features"]
    assert s.lines == {street_names.GATUNAMN: n}
    info = pyogrio.read_info(out, layer=street_names.GATUNAMN)
    assert info["fields"].tolist() == ["Namn"]
    assert info["geometry_type"] == "LineString"
    # FileGDB snaps coordinates to its grid, so compare length rather than exact lines.
    length = shapely.length(shapely.from_wkb(pyogrio.raw.read(out, layer=info["layer_name"])[2]))
    fixture = shapely.length(
        shapely.from_wkb(pyogrio.raw.read(FIXTURE, layer=street_names.GATUNAMN)[2])
    )
    assert length.sum() == pytest.approx(fixture.sum(), rel=1e-6)


def test_rejects_empty_county_zip(tmp_path):
    """Like Lastkajen's Dalarna GeoPackage zip: info files only."""
    z = tmp_path / "Dalarnas_län_GeoPackage.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("Licensinformation.txt", "CC0")
    with pytest.raises(ValueError, match="FileGDB"):
        extract([z], tmp_path / "out.gpkg", log=lambda *_: None)
