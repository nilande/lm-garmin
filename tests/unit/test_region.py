import pytest

from lm_garmin import region


def test_parse_bbox():
    assert region.parse_bbox("500000, 7250000,550000,7310000") == (500000, 7250000, 550000, 7310000)


@pytest.mark.parametrize("bad", ["1,2,3", "5,2,3,4", "1,4,3,2", "a,b,c,d"])
def test_parse_bbox_rejects(bad):
    with pytest.raises(ValueError):
        region.parse_bbox(bad)


def test_region_id_is_stable():
    assert (
        region.from_bbox("500000,7250000,550000,7310000").id == "bbox-500000-7250000-550000-7310000"
    )
    assert region.Region("sweden", (0, 0, 1, 1)).id == "sweden"


def test_from_wgs84_encloses_corners():
    r = region.from_wgs84("15.0,65.5,15.5,65.7")
    xmin, ymin, xmax, ymax = r.bbox
    # Hemavan area: roughly E 500 km, N 7 265 km in SWEREF 99 TM
    assert 480_000 < xmin < xmax < 540_000
    assert 7_260_000 < ymin < ymax < 7_300_000


def test_sweden_from_gpkg_contents(data_dir, tmp_path):
    import shutil

    shutil.copy(data_dir / "skoter_730_51.gpkg", tmp_path)
    r = region.sweden(tmp_path)
    assert r.id == "sweden"
    x0, y0, x1, y1 = r.bbox
    assert x0 <= 510_000 and x1 >= 519_000 and y0 <= 7_301_000 and y1 >= 7_309_000
