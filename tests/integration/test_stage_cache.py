import shutil
import sqlite3
from pathlib import Path

import pytest

from lm_garmin import products, tools
from lm_garmin.build import build
from lm_garmin.region import Region
from lm_garmin.stage_cache import StageCache

pytestmark = pytest.mark.integration


def test_style_only_rebuild_reuses_conversion_and_tiles(data_dir, tmp_path, monkeypatch):
    if not tools.find_java():
        pytest.skip("java not found")
    source = tmp_path / "data"
    source.mkdir()
    shutil.copyfile(data_dir / "fjall_727_51_05.gpkg", source / "fixture.gpkg")
    styles = tmp_path / "styles"
    shutil.copytree(products.STYLES_DIR, styles)
    monkeypatch.setattr(products, "STYLES_DIR", styles)
    out = tmp_path / "out"
    cache = tmp_path / "cache"
    region = Region("test", (515000, 7270000, 520000, 7275000))

    def run(r=region):
        return [
            step["cached"]
            for step in build(source, r, out, cache, products=["topo50"], jobs=1)["steps"]
        ]

    assert run() == [False, False, False]
    assert run() == [True, True, True]
    cold = (out / "lm-topo50.img").read_bytes()
    mapping = styles / "topo50" / "mapping.csv"
    mapping.write_text(mapping.read_text().replace("#CBEAFF", "#80B4E0"))
    assert run() == [True, True, False]
    assert (out / "lm-topo50.img").read_bytes() != cold
    assert run(Region(region.name, (515000, 7270000, 519000, 7275000))) == [False, False, False]
    assert run() == [True, True, True]

    with StageCache(cache).lease():
        details = StageCache(cache).info()
    assert details["convert"]["entries"] == 2
    assert details["split"]["entries"] == 2
    assert details["compile"]["entries"] == 3
    with sqlite3.connect(source / "fixture.gpkg") as db:
        db.execute("UPDATE gpkg_contents SET description = 'changed source'")
    assert run() == [False, False, False]
    StageCache(cache).clean()
    assert StageCache(cache).info() == {}
    assert (out / "lm-topo50.img").is_file()


def test_failed_or_incomplete_stage_is_never_a_cache_hit(tmp_path):
    cache = StageCache(tmp_path)

    def complete(path: Path):
        (path / "part").write_text("complete")
        return {"ok": True}

    def fail(path: Path):
        (path / "part").write_text("partial")
        raise RuntimeError("failed")

    with cache.lease():
        with pytest.raises(RuntimeError, match="failed"):
            cache.run("convert", "data", fail)
        built = cache.run("convert", "data", complete)
        assert not built.cached
        assert cache.run("convert", "data", fail).cached
        (built.path / "part").unlink()
        assert not cache.run("convert", "data", complete).cached
