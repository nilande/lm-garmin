"""Extract only the NVDB name layers from Lastkajen county deliveries (issue #60).

A county GeoPackage from Lastkajen (*Länsfiler NVDB-data*) is 0.2–2.2 GB unpacked and has
about 124 layers; street names need two of them. `extract` reads the county zips (or
unpacked GeoPackages) one at a time and writes one small GeoPackage with
`NVDB_DK_O_20_Gatunamn` and `NVDB_DK_O_21_Ovrigt_vagnamn` (name column only, 2D lines),
which `--nvdb-dir` then uses. A JSON sidecar records the sources and counts.

The nationwide *Sverigefiler utvalda NVDB-data* have no name layers; the 21 county
packages (GeoPackage format) together cover Sweden.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pyogrio
import shapely

from .street_names import GATUNAMN, LAYERS, NAME_FIELD, tables
from .tools import sha256_file


@dataclass
class Source:
    file: str
    sha256: str
    lines: dict[str, int] = field(default_factory=dict)


def _gpkg_members(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    return [
        m
        for m in zf.infolist()
        if m.filename.lower().endswith(".gpkg") and not Path(m.filename).name.startswith("._")
    ]


def _inputs(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files += sorted(
                f
                for f in p.iterdir()
                if f.suffix.lower() in (".zip", ".gpkg") and not f.name.startswith("._")
            )
        else:
            files.append(p)
    if not files:
        raise FileNotFoundError("no .zip or .gpkg inputs")
    return files


def _copy_layers(gpkg: Path, out: Path, source: Source) -> None:
    available = tables(gpkg)
    if GATUNAMN not in available:
        raise ValueError(f"{source.file}: no layer {GATUNAMN} – is it an NVDB county file?")
    for layer in LAYERS:
        if layer not in available:
            continue
        meta, _, wkb, fields = pyogrio.raw.read(gpkg, layer=layer, columns=[NAME_FIELD])
        if meta["crs"] != "EPSG:3006":
            raise ValueError(f"{source.file}:{layer} must use SWEREF 99 TM (EPSG:3006)")
        geoms = shapely.force_2d(shapely.from_wkb(wkb)) if wkb is not None else np.array([])
        names = np.asarray(fields[0], dtype=object)
        keep = np.array(
            [
                g is not None and not g.is_empty and bool((n or "").strip())
                for g, n in zip(geoms, names, strict=True)
            ],
            dtype=bool,
        )
        source.lines[layer] = int(keep.sum())
        if not keep.any():
            continue
        pyogrio.raw.write(
            out,
            geometry=shapely.to_wkb(geoms[keep]),
            field_data=[names[keep]],
            fields=[NAME_FIELD],
            layer=layer,
            driver="GPKG",
            geometry_type="LineString",
            crs="EPSG:3006",
            append=layer in tables(out) if out.exists() else False,
        )


def extract(paths: list[Path], out: Path, log=print) -> list[Source]:
    """Write the name layers of all inputs to `out` (replaced if it exists)."""
    files = _inputs(paths)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = out.with_name(out.stem + ".part.gpkg")
    tmp_out.unlink(missing_ok=True)
    sources: list[Source] = []
    try:
        for f in files:
            source = Source(f.name, sha256_file(f))
            if f.suffix.lower() == ".gpkg":
                _copy_layers(f, tmp_out, source)
            else:
                with zipfile.ZipFile(f) as zf, tempfile.TemporaryDirectory(dir=out.parent) as td:
                    members = _gpkg_members(zf)
                    if len(members) != 1:
                        raise ValueError(f"{f.name}: expected one .gpkg, found {len(members)}")
                    target = Path(td) / "county.gpkg"
                    with zf.open(members[0]) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst, 16 * 1024 * 1024)
                    _copy_layers(target, tmp_out, source)
            sources.append(source)
            log(f"{f.name}: " + ", ".join(f"{k} {v}" for k, v in source.lines.items()))
        tmp_out.replace(out)
    finally:
        tmp_out.unlink(missing_ok=True)
    sidecar = out.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {"layers": list(LAYERS), "sources": [asdict(s) for s in sources]},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return sources
