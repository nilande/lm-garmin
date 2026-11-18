import shutil
import sqlite3
import zipfile

import pytest

from lm_garmin.unpack import check_gpkg, unpack


@pytest.fixture
def delivery(tmp_path, data_dir):
    d = tmp_path / "LM2026:1 - Topografi 50 Nedladdning, vektor"
    d.mkdir()
    gpkg = data_dir / "fjall_727_51_05.gpkg"
    with zipfile.ZipFile(d / "hojd_sverige.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(gpkg, "hojd_sverige.gpkg")
        z.writestr("._hojd_sverige.gpkg", b"appledouble")
    (d / "._hojd_sverige.zip").write_bytes(b"junk")
    (d / ".DS_Store").write_bytes(b"junk")
    (d / "uttag.json").write_text("{}")
    return d


def test_unpack_and_skip_unchanged(delivery, tmp_path):
    dest = tmp_path / "cache"
    first = unpack(delivery, dest, log=lambda *_: None)
    assert [r.gpkg.name for r in first] == ["hojd_sverige.gpkg"]
    assert not first[0].skipped
    assert not list(dest.glob("._*"))
    second = unpack(delivery, dest, log=lambda *_: None)
    assert second[0].skipped
    assert (dest / "manifest.json").exists()


def test_check_gpkg_requires_rtree(tmp_path, data_dir):
    g = tmp_path / "x.gpkg"
    shutil.copy(data_dir / "fjall_727_51_05.gpkg", g)
    check_gpkg(g)
    with sqlite3.connect(g) as c:
        c.execute("DROP TABLE rtree_hojdlinje_geom")
    with pytest.raises(ValueError, match="rtree_hojdlinje_geom"):
        check_gpkg(g)


def test_zip_must_hold_one_gpkg(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    with zipfile.ZipFile(d / "x.zip", "w") as z:
        z.writestr("readme.txt", "no gpkg")
    with pytest.raises(ValueError, match="exactly one"):
        unpack(d, tmp_path / "c", log=lambda *_: None)
