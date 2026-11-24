import zipfile

import numpy as np

from lm_garmin import dem

# A 2 x 2 km patch near Storuman, inside grid 50+ square 72_5 (N 7 200–7 300 km, E 500–600 km).
E0, N0 = 540_000, 7_250_000


def _square_zip(path, rows):
    with zipfile.ZipFile(path, "w") as z:
        text = "\n".join(f"{x:.1f} {y:.1f} {h:.2f}".replace(".", ",") for x, y, h in rows)
        z.writestr("72_5.xyz", text + "\n")
    return path


def _slope(x, y):
    return 400 + (x - E0) / 10 + (y - N0) / 20  # metres; rises east and north


def _patch(step=50, size=2000, skip=()):
    for i in range(size // step):
        for j in range(size // step):
            if (i, j) in skip:
                continue
            x, y = E0 + i * step + 25.3, N0 + j * step + 24.8
            yield x, y, _slope(x, y)


def test_squares_parse_delivery_names(tmp_path):
    for name in ("71_5.zip", "61_3.zip", "notes.zip", "71_5.txt"):
        (tmp_path / name).write_bytes(b"")
    assert sorted(dem.squares(tmp_path)) == [(61, 3), (71, 5)]


def test_tile_names():
    assert dem.tile_name((65, 16)) == "N65E016"
    assert dem.tile_name((-3, -7)) == "S03W007"


def test_plan_lists_tiles_and_their_squares():
    available = {(72, 5): None, (72, 6): None}
    plan = dem.plan((E0, N0, E0 + 2000, N0 + 2000), available)
    assert list(plan) == [(65, 15)]
    assert plan[(65, 15)] == [(72, 5)]
    assert dem.plan((E0, N0, E0 + 2000, N0 + 2000), {(71, 5): None}) == {}


def test_read_square_bins_points_and_fills_gaps(tmp_path):
    z = _square_zip(tmp_path / "72_5.zip", _patch(skip={(10, 10)}))
    grid = dem.read_square(z, (72, 5))
    assert grid.shape == (dem.CELLS, dem.CELLS) and grid.dtype == np.int16
    row = (73 * dem.SQUARE - (N0 + 25)) // dem.CELL  # cell of the first point
    col = (E0 - 5 * dem.SQUARE) // dem.CELL
    assert grid[row, col] == round(_slope(E0 + 25.3, N0 + 24.8))
    gap = grid[row - 10, col + 10]  # the skipped point, filled from its neighbours
    assert abs(gap - _slope(E0 + 525, N0 + 525)) <= 1
    assert (grid == dem.VOID).sum() == dem.CELLS**2 - 40 * 40


def test_write_tiles_makes_srtm_hgt(tmp_path):
    z = _square_zip(tmp_path / "72_5.zip", _patch())
    available = {(72, 5): z}
    plan = dem.plan((E0, N0, E0 + 2000, N0 + 2000), available)
    [path] = dem.write_tiles(available, plan, tmp_path / "hgt", log=lambda _: None)
    assert path.name == "N65E015.hgt"
    assert path.stat().st_size == 2 * dem.HGT_SIZE**2
    hgt = np.fromfile(path, ">i2").reshape(dem.HGT_SIZE, dem.HGT_SIZE)
    lon, lat = dem._to_wgs84.transform(E0 + 1000, N0 + 1000)
    row = round((65 + 1 - lat) * 3600)
    col = round((lon - 15) * 3600)
    assert abs(hgt[row, col] - _slope(E0 + 1000, N0 + 1000)) <= 2
    assert (hgt != dem.VOID).sum() < 0.01 * hgt.size  # only the patch has data
