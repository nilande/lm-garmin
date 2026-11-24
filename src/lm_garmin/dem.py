"""Elevation tiles for terrain shading (issue #90).

The source is Lantmäteriet's *Markhöjdmodell Nedladdning, grid 50+*: one zip per
100 x 100 km square, named `<N/100 km>_<E/100 km>.zip` (so `71_5` covers N 7 100–7 200 km,
E 500–600 km in SWEREF 99 TM). Each holds one `.xyz` text file of `x y z` rows with decimal
commas, heights in metres above sea level (RH 2000). The points are about 50 m apart but on
a slightly rotated grid, so they are binned into 50 m SWEREF 99 TM cells (the mean of the
points in a cell); the few empty cells inside the data are filled from their neighbours.

mkgmap's `--dem` reads SRTM-style `.hgt` tiles: 1° x 1° in WGS 84, named after the
south-west corner (`N65E016.hgt`), 3601 x 3601 big-endian int16 samples (1 arc second)
whose outer rows and columns are shared with the neighbouring tiles. Cells without data are
voids (-32768).
"""

from __future__ import annotations

import math
import re
import zipfile
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

import numpy as np
from pyproj import Transformer
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

CELL = 50  # m
SQUARE = 100_000  # m, one source zip
CELLS = SQUARE // CELL
HGT_SIZE = 3601
VOID = -32768
SQUARE_NAME = re.compile(r"^(\d{2})_(\d{1,2})\.zip$")

Square = tuple[int, int]  # (north, east) in units of 100 km
Tile = tuple[int, int]  # (lat, lon) of the south-west corner

_to_wgs84 = Transformer.from_crs(3006, 4326, always_xy=True)
_to_sweref = Transformer.from_crs(4326, 3006, always_xy=True)


def squares(src_dir: Path) -> dict[Square, Path]:
    """The source zips in a grid 50+ delivery folder, by square."""
    found = {}
    for path in src_dir.glob("*.zip"):
        if m := SQUARE_NAME.match(path.name):
            found[int(m[1]), int(m[2])] = path
    return found


def tile_name(tile: Tile) -> str:
    lat, lon = tile
    return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"


def _outline(xmin: float, ymin: float, xmax: float, ymax: float, n: int = 16) -> tuple:
    t = np.linspace(0.0, 1.0, n)
    xs = np.concatenate(
        [xmin + (xmax - xmin) * t, np.full(n, xmax), xmax - (xmax - xmin) * t, np.full(n, xmin)]
    )
    ys = np.concatenate(
        [np.full(n, ymin), ymin + (ymax - ymin) * t, np.full(n, ymax), ymax - (ymax - ymin) * t]
    )
    return xs, ys


def tiles_for(bbox: tuple[float, float, float, float]) -> list[Tile]:
    """HGT tiles covering a SWEREF 99 TM bbox."""
    lon, lat = _to_wgs84.transform(*_outline(*bbox))
    return [
        (la, lo)
        for la in range(math.floor(min(lat)), math.floor(max(lat)) + 1)
        for lo in range(math.floor(min(lon)), math.floor(max(lon)) + 1)
    ]


def tile_bounds(tile: Tile) -> tuple[float, float, float, float]:
    """SWEREF 99 TM bbox of an HGT tile (including its half-sample border)."""
    lat, lon = tile
    h = 0.5 / 3600
    x, y = _to_sweref.transform(*_outline(lon - h, lat - h, lon + 1 + h, lat + 1 + h))
    return min(x), min(y), max(x), max(y)


def squares_for(bounds: tuple[float, float, float, float]) -> list[Square]:
    xmin, ymin, xmax, ymax = bounds
    return [
        (n, e)
        for n in range(math.floor(ymin / SQUARE), math.floor(ymax / SQUARE) + 1)
        for e in range(math.floor(xmin / SQUARE), math.floor(xmax / SQUARE) + 1)
    ]


def plan(
    bbox: tuple[float, float, float, float], available: dict[Square, Path]
) -> dict[Tile, list[Square]]:
    """The tiles for a bbox and the available source squares each one needs.

    Tiles that touch no source square are left out.
    """
    out = {}
    for tile in tiles_for(bbox):
        need = [s for s in squares_for(tile_bounds(tile)) if s in available]
        if need:
            out[tile] = need
    return out


def read_square(path: Path, square: Square) -> np.ndarray:
    """Bin one source square into a CELLS x CELLS int16 grid (row 0 = north)."""
    with zipfile.ZipFile(path) as z:
        member = next(n for n in z.namelist() if n.lower().endswith(".xyz"))
        data = z.read(member)
    values = np.array(data.replace(b",", b".").split(), dtype=np.float64)
    if values.size % 3:
        raise ValueError(f"{path.name}: expected x y z rows")
    x, y, h = values.reshape(-1, 3).T
    n, e = square
    col = np.floor((x - e * SQUARE) / CELL).astype(np.int64)
    row = np.floor(((n + 1) * SQUARE - y) / CELL).astype(np.int64)
    ok = (col >= 0) & (col < CELLS) & (row >= 0) & (row < CELLS)
    idx = row[ok] * CELLS + col[ok]
    total = np.bincount(idx, weights=h[ok], minlength=CELLS * CELLS)
    count = np.bincount(idx, minlength=CELLS * CELLS)
    grid = np.full(CELLS * CELLS, np.nan)
    has = count > 0
    grid[has] = total[has] / count[has]
    grid = _fill(grid.reshape(CELLS, CELLS))
    out = np.full(grid.shape, VOID, dtype=np.int16)
    valid = ~np.isnan(grid)
    out[valid] = np.round(grid[valid]).astype(np.int16)
    return out


def _fill(grid: np.ndarray, passes: int = 2) -> np.ndarray:
    """Fill empty cells surrounded by data (5+ of 8 neighbours) with their mean."""
    for _ in range(passes):
        empty = np.isnan(grid)
        if not empty.any():
            break
        padded = np.pad(grid, 1, constant_values=np.nan)
        stack = np.stack(
            [
                padded[1 + dy : 1 + dy + grid.shape[0], 1 + dx : 1 + dx + grid.shape[1]]
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
                if dy or dx
            ]
        )
        count = (~np.isnan(stack)).sum(axis=0)
        total = np.nansum(stack, axis=0)
        fill = empty & (count >= 5)  # gaps inside the data, not its edges
        grid = grid.copy()
        grid[fill] = total[fill] / count[fill]
    return grid


def write_tiles(
    available: dict[Square, Path],
    tiles: dict[Tile, list[Square]],
    out_dir: Path,
    log: Callable[[str], None] = print,
    keep: int = 12,
) -> list[Path]:
    """Write one .hgt per tile; tiles without any data are skipped."""
    out_dir.mkdir(parents=True, exist_ok=True)
    loaded: OrderedDict[Square, np.ndarray] = OrderedDict()

    def square(s: Square) -> np.ndarray:
        if s in loaded:
            loaded.move_to_end(s)
        else:
            loaded[s] = read_square(available[s], s)
            if len(loaded) > keep:
                loaded.popitem(last=False)
        return loaded[s]

    written = []
    for tile in sorted(tiles):
        need = tiles[tile]
        ns = [n for n, _ in need]
        es = [e for _, e in need]
        n0, n1, e0, e1 = min(ns), max(ns), min(es), max(es)
        mosaic = np.full(((n1 - n0 + 1) * CELLS, (e1 - e0 + 1) * CELLS), VOID, dtype=np.int16)
        for n, e in need:
            r = (n1 - n) * CELLS
            c = (e - e0) * CELLS
            mosaic[r : r + CELLS, c : c + CELLS] = square((n, e))
        lat, lon = tile
        h = 0.5 / 3600
        hgt = np.full((HGT_SIZE, HGT_SIZE), VOID, dtype=np.int16)
        reproject(
            source=mosaic,
            destination=hgt,
            src_transform=from_origin(e0 * SQUARE, (n1 + 1) * SQUARE, CELL, CELL),
            src_crs="EPSG:3006",
            src_nodata=VOID,
            dst_transform=from_origin(lon - h, lat + 1 + h, 1 / 3600, 1 / 3600),
            dst_crs="EPSG:4326",
            dst_nodata=VOID,
            resampling=Resampling.bilinear,
        )
        if (hgt == VOID).all():
            continue
        path = out_dir / f"{tile_name(tile)}.hgt"
        hgt.astype(">i2").tofile(path)
        written.append(path)
        log(f"dem: {path.name} ({(hgt != VOID).mean():.0%} data)")
    return written
