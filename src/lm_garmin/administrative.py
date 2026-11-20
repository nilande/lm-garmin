"""Resolve named regions from Topografi 50 boundary lines and the SCB name index."""

from pathlib import Path
from unicodedata import normalize
from zipfile import BadZipFile, ZipFile

import numpy as np
import pyogrio
import shapely

from .region import Region

BOUNDARY_CODES = (1561, 1562, 1563)
INDEX_LAYERS = {
    "county": ("LanSweref99TM.zip", "LnKod", "LnNamn"),
    "municipality": ("Kommun_Sweref99TM.zip", "KnKod", "KnNamn"),
}


def _key(name: str, kind: str) -> str:
    key = normalize("NFC", " ".join(name.split())).casefold()
    return key.removesuffix(" län") if kind == "county" else key


def _geometries(meta, table):
    return shapely.from_wkb(table[meta["geometry_name"] or "wkb_geometry"].to_pylist())


def _named_shapes(index: Path, kind: str):
    member, code_column, name_column = INDEX_LAYERS[kind]
    try:
        with ZipFile(index) as bundle:
            meta, table = pyogrio.read_arrow(
                bundle.read(member), columns=[code_column, name_column]
            )
        codes = table[code_column].to_pylist()
        names = table[name_column].to_pylist()
        geometry = shapely.make_valid(_geometries(meta, table))
    except (OSError, BadZipFile, KeyError, RuntimeError) as e:
        raise ValueError(f"Cannot read the SCB digital boundaries ZIP {index}: {e}") from e
    return codes, names, geometry


def _topo50_faces(path: Path, kind: str):
    codes = BOUNDARY_CODES if kind == "county" else (*BOUNDARY_CODES, 1564)
    meta, table = pyogrio.read_arrow(
        path,
        layer="administrativ_grans",
        columns=[],
        where=f"objekttypnr IN {codes}",
        IMMUTABLE="YES",
    )
    if meta["crs"] != "EPSG:3006":
        raise ValueError(f"{path} must use SWEREF 99 TM (EPSG:3006)")
    # Node every intersection before extracting the closed faces. Use the delivered coordinates.
    network = shapely.union_all(_geometries(meta, table))
    return shapely.get_parts(shapely.polygonize(shapely.get_parts(network)))


def _match_faces(references, faces):
    assigned = {}
    tree = shapely.STRtree(references)
    for face in faces:
        indices = tree.query(face, predicate="intersects")
        if not len(indices):
            continue
        overlaps = shapely.area(shapely.intersection(face, references[indices]))
        best = int(np.argmax(overlaps))
        # A missing dividing line can merge two jurisdictions into one face.
        if overlaps[best] > 0 and overlaps[best] >= 0.8 * overlaps.sum():
            assigned.setdefault(indices[best], []).append(face)
    return assigned


def named_regions(kind: str, names: list[str], gpkg_dir: Path, index: Path) -> list[Region]:
    """Prefer the precise closed faces, with the named SCB polygon as the fallback."""
    codes, display_names, references = _named_shapes(index, kind)
    by_name = {_key(name, kind): i for i, name in enumerate(display_names)}
    by_code = {code: i for i, code in enumerate(codes)}
    requested = []
    for name in names:
        lookup = _key(name, kind)
        i = by_code.get(lookup, by_name.get(lookup))
        if i is None:
            raise ValueError(f"Unknown {kind}: {name!r}. Use a name or code from the SCB index.")
        requested.append(i)

    path = gpkg_dir / "administrativindelning_sverige.gpkg"
    assigned = _match_faces(references, _topo50_faces(path, kind)) if path.is_file() else {}
    output = []
    for i in dict.fromkeys(requested):
        reference = references[i]
        face = shapely.union_all(assigned.get(i, []))
        if not face.is_empty and face.intersection(reference).area >= 0.8 * reference.area:
            geometry, source = face, "Topografi 50"
        else:
            geometry, source = reference, "SCB simplified boundary"
        if geometry.is_empty or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"No usable {kind} geometry for {display_names[i]}")
        output.append(Region(f"{kind}-{codes[i]}", geometry.bounds, geometry, source))
    return output
