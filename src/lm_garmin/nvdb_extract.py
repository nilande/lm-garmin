"""Extract only the NVDB name layers from Lastkajen county deliveries (issue #60).

A county GeoPackage from Lastkajen (*Länsfiler NVDB-data*) is 0.2–2.2 GB unpacked and has
about 124 layers; street names need two of them. `extract` reads the county zips (or
unpacked GeoPackages) one at a time and writes one small GeoPackage with
`NVDB_DK_O_20_Gatunamn` and `NVDB_DK_O_21_Ovrigt_vagnamn` (name column only, 2D lines),
which `--nvdb-dir` then uses. A JSON sidecar records the sources, counts and each delivery's
*Betraktelsedatum* (from `Leveransinformation_*.txt`; FileGDB zips have no such file).

Each county comes as a GeoPackage zip and a File Geodatabase zip with the same content. Both
are read; the FileGDB names the layers `TNE_FT_Gatunamn_1` and `TNE_FT_Ovrigt_vagnamn_1` and
the name column `Namn_<n>`. (The Lastkajen GeoPackage zip of Dalarnas län has no .gpkg, so
that county needs the FileGDB.)

The nationwide *Sverigefiler utvalda NVDB-data* have no name layers; the 21 county
packages together cover Sweden.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import warnings
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pyogrio
import shapely

from .street_names import (
    CITY_FIELD,
    GATUNAMN,
    LAYERS,
    NAME_FIELD,
    OVRIGT_VAGNAMN,
    REGION_FIELD,
    tables,
)
from .tools import sha256_file

# FileGDB layer names of the same NVDB name layers.
FILEGDB_LAYERS = {GATUNAMN: "TNE_FT_Gatunamn_1", OVRIGT_VAGNAMN: "TNE_FT_Ovrigt_vagnamn_1"}
# Municipality and county per road element (#72): GeoPackage and FileGDB form.
PLACES_LAYER = "AGGREGAT_O_5_KommunLanReg"
PLACES_FILEGDB = "TNE_FT_KOMMUNLANREG_5_100106"


@dataclass
class Source:
    file: str
    sha256: str
    lines: dict[str, int] = field(default_factory=dict)
    betraktelsedatum: str | None = None
    placed: dict[str, int] = field(default_factory=dict)  # lines with municipality and county


_DATE = re.compile(r"Betraktelsedatum:\s*(\d{4}-\d{2}-\d{2})")


def _delivery_date(zf: zipfile.ZipFile) -> str | None:
    """Betraktelsedatum from Lastkajen's `Leveransinformation_*.txt`, if the zip has one."""
    for m in zf.infolist():
        name = Path(m.filename).name
        if name.startswith("Leveransinformation") and name.lower().endswith(".txt"):
            found = _DATE.search(zf.read(m).decode("utf-8-sig", errors="replace"))
            if found:
                return found.group(1)
    return None


def _gpkg_members(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    return [
        m
        for m in zf.infolist()
        if m.filename.lower().endswith(".gpkg") and not Path(m.filename).name.startswith("._")
    ]


def _gdb_dirs(zf: zipfile.ZipFile) -> list[str]:
    """Top-level-or-nested `*.gdb` folders in a zip, as paths inside the zip."""
    dirs = set()
    for name in zf.namelist():
        parts = name.split("/")
        for i, part in enumerate(parts[:-1]):
            if part.lower().endswith(".gdb") and not part.startswith("._"):
                dirs.add("/".join(parts[: i + 1]))
                break
    return sorted(dirs)


def _is_input(f: Path) -> bool:
    return not f.name.startswith("._") and f.suffix.lower() in (".zip", ".gpkg", ".gdb")


def _inputs(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir() and p.suffix.lower() != ".gdb":
            files += sorted(f for f in p.iterdir() if _is_input(f))
        else:
            files.append(p)
    if not files:
        raise FileNotFoundError("no .zip, .gpkg or .gdb inputs")
    return files


def _layers(src: str) -> dict[str, tuple[str, str]]:
    """Map each available NVDB name layer to (source layer, name column) in `src`."""
    if src.lower().endswith(".gpkg"):
        available = tables(Path(src))
        return {lyr: (lyr, NAME_FIELD) for lyr in LAYERS if lyr in available}
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "Measured", UserWarning)
        available = set(pyogrio.list_layers(src)[:, 0])
    found: dict[str, tuple[str, str]] = {}
    for lyr, gdb_layer in FILEGDB_LAYERS.items():
        if gdb_layer in available:
            fields = pyogrio.read_info(src, layer=gdb_layer)["fields"]
            name = next((f for f in fields if f == NAME_FIELD or f.startswith("Namn_")), None)
            if name:
                found[lyr] = (gdb_layer, name)
    return found


def _key_field(fields) -> str | None:
    """Road-element id: ELEMENT_ID in GeoPackages, ROUTE_ID in FileGDBs (same values)."""
    return next((f for f in ("ELEMENT_ID", "ROUTE_ID") if f in fields), None)


def _places(src: str) -> dict[str, tuple[str, str]]:
    """Road-element id → (municipality, county) from KommunLanReg; {} if the layer is missing."""
    gpkg = src.lower().endswith(".gpkg")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "Measured", UserWarning)
        available = tables(Path(src)) if gpkg else set(pyogrio.list_layers(src)[:, 0])
        layer = PLACES_LAYER if gpkg else PLACES_FILEGDB
        if layer not in available:
            return {}
        fields = list(pyogrio.read_info(src, layer=layer)["fields"])
        key = _key_field(fields)
        if gpkg:
            city, region = "Kommunnamn", "Lansnamn"
        else:  # numbered columns: Kommu_<n> holds the name, Kommu_<n+1> the code
            city = min((f for f in fields if f.startswith("Kommu_")), default=None)
            region = next((f for f in fields if f.startswith("Lansn_")), None)
        if not key or city not in fields or region not in fields:
            return {}
        meta, _, _, data = pyogrio.raw.read(
            src, layer=layer, read_geometry=False, columns=[key, city, region]
        )
    cols = dict(zip(list(meta["fields"]), data, strict=True))
    out: dict[str, tuple[str, str]] = {}
    for k, c, r in zip(cols[key], cols[city], cols[region], strict=True):
        if k and c and r:
            out.setdefault(str(k), (str(c), str(r)))
    return out


def _copy_layers(src: str, out: Path, source: Source) -> None:
    layers = _layers(src)
    places = _places(src)
    if GATUNAMN not in layers:
        raise ValueError(f"{source.file}: no layer {GATUNAMN} – is it an NVDB county file?")
    for layer, (src_layer, name_field) in layers.items():
        with warnings.catch_warnings():  # FileGDB lines are measured (M); M is dropped
            warnings.filterwarnings("ignore", "Measured", UserWarning)
            key = _key_field(pyogrio.read_info(src, layer=src_layer)["fields"])
            meta, _, wkb, fields = pyogrio.raw.read(
                src, layer=src_layer, columns=[name_field, *([key] if key else [])]
            )
        if meta["crs"] != "EPSG:3006":
            raise ValueError(f"{source.file}:{layer} must use SWEREF 99 TM (EPSG:3006)")
        geoms = shapely.force_2d(shapely.from_wkb(wkb)) if wkb is not None else np.array([])
        # pyogrio returns columns in source order, not in the order asked for.
        cols = dict(zip(list(meta["fields"]), fields, strict=True))
        names = np.asarray(cols[name_field], dtype=object)
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
        found = [places.get(str(k)) for k in cols[key]] if key else [None] * len(names)
        city = np.array([p[0] if p else None for p in found], dtype=object)
        region = np.array([p[1] if p else None for p in found], dtype=object)
        source.placed[layer] = sum(1 for p, k in zip(found, keep, strict=True) if p and k)
        # FileGDB delivers MultiLineStrings: store single lines, as the layer type says.
        parts, index = shapely.get_parts(geoms[keep], return_index=True)
        pyogrio.raw.write(
            out,
            geometry=shapely.to_wkb(parts),
            field_data=[names[keep][index], city[keep][index], region[keep][index]],
            fields=[NAME_FIELD, CITY_FIELD, REGION_FIELD],
            layer=layer,
            driver="GPKG",
            geometry_type="LineString",
            crs="EPSG:3006",
            append=layer in tables(out) if out.exists() else False,
        )


def _copy_zip(f: Path, out: Path, source: Source) -> None:
    """A county zip with one GeoPackage (unpacked to a temp file) or one FileGDB (read in place)."""
    with zipfile.ZipFile(f) as zf:
        members = _gpkg_members(zf)
        gdbs = _gdb_dirs(zf)
        source.betraktelsedatum = _delivery_date(zf)
    if len(members) == 1:
        with zipfile.ZipFile(f) as zf, tempfile.TemporaryDirectory(dir=out.parent) as td:
            target = Path(td) / "county.gpkg"
            with zf.open(members[0]) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, 16 * 1024 * 1024)
            _copy_layers(str(target), out, source)
    elif not members and len(gdbs) == 1:
        _copy_layers(f"/vsizip/{f.resolve()}/{gdbs[0]}", out, source)
    else:
        raise ValueError(
            f"{f.name}: expected one .gpkg or one .gdb, found {len(members)} .gpkg "
            f"and {len(gdbs)} .gdb – Lastkajen's Dalarna GeoPackage zip is empty; use its FileGDB"
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
            if f.suffix.lower() == ".gdb":
                source = Source(f.name, "")  # a folder: no single checksum
                _copy_layers(str(f), tmp_out, source)
            elif f.suffix.lower() == ".gpkg":
                source = Source(f.name, sha256_file(f))
                _copy_layers(str(f), tmp_out, source)
            else:
                source = Source(f.name, sha256_file(f))
                _copy_zip(f, tmp_out, source)
            sources.append(source)
            date = source.betraktelsedatum or "no Betraktelsedatum"
            log(f"{f.name} ({date}): " + ", ".join(f"{k} {v}" for k, v in source.lines.items()))
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
