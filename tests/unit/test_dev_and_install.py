import pytest

from lm_garmin import region
from lm_garmin.install import install
from lm_garmin.products import PRODUCTS, dev_variant


def test_dev_variant_has_own_ids_and_file():
    dev_filenames = {
        "topo50": "lm-dev-topo50.img",
        "skoter": "lm-dev-skoter.img",
        "skoter-osm": "osm-dev-skoter.img",
    }
    for p in PRODUCTS.values():
        d = dev_variant(p)
        assert d.family_id == p.family_id + 2
        assert d.mapid_base // 10_000 == d.family_id
        assert d.filename == dev_filenames[p.key]
        assert "(dev)" in d.name
    fams = {p.family_id for p in PRODUCTS.values()} | {
        dev_variant(p).family_id for p in PRODUCTS.values()
    }
    assert len(fams) == 2 * len(PRODUCTS)


def test_named_areas():
    r = region.from_area("taby")
    assert r.id == "taby" and r.bbox[0] < 670000 < r.bbox[2]
    with pytest.raises(ValueError, match="unknown area"):
        region.from_area("nowhere")


def test_install_copies_verifies_and_removes_appledouble(tmp_path):
    dev = tmp_path / "GARMIN"
    (dev / "Garmin").mkdir(parents=True)
    (dev / "Garmin" / "._lm-dev-topo50.img").write_bytes(b"junk")
    (dev / "Garmin" / "lm-dev-topo50.img").write_bytes(b"old")
    src = tmp_path / "lm-dev-topo50.img"
    src.write_bytes(b"new map" * 1000)
    out = install([src], dev, log=lambda *_: None)
    assert out[0].read_bytes() == src.read_bytes()
    assert sorted(p.name for p in (dev / "Garmin").iterdir()) == ["lm-dev-topo50.img"]


def test_install_requires_mounted_device(tmp_path):
    src = tmp_path / "x.img"
    src.write_bytes(b"x")
    with pytest.raises(FileNotFoundError, match="connected"):
        install([src], tmp_path / "missing", log=lambda *_: None)
