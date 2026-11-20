"""Prepare build-only polygons from the nationwide Topografi 100 and 250 deliveries."""

from pathlib import Path

import pyogrio
import shapely
from pyproj import Transformer
from shapely.geometry import box

from .convert import BATCH_SIZE, ID_STRIDE, THEMES, OsmSink, _to_wgs84
from .region import Region

RESOLUTIONS = {100: 20, 250: 18}
LAYERS = ("mark", "sankmark")


def _polygons(geometry):
    if geometry is None or geometry.is_empty:
        return
    if geometry.geom_type == "Polygon":
        yield geometry
    elif geometry.geom_type in {"MultiPolygon", "GeometryCollection"}:
        for part in shapely.get_parts(geometry):
            yield from _polygons(part)


def write_polygons(
    sources: dict[int, Path], region: Region, dest: Path, mapped: dict[str, set[str]]
) -> dict[int, int]:
    """Append a separate PBF to the base-map inputs, without changing the Topografi 50 cache."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    project = Transformer.from_crs(3006, 4326, always_xy=True)
    extent = box(*region.bbox)
    sink = OsmSink(dest, (len(THEMES) + 1) * ID_STRIDE, project.transform_bounds(*region.bbox))
    counts = dict.fromkeys(sources, 0)
    try:
        for scale, path in sources.items():
            for layer in LAYERS:
                tagged_layer = f"{layer}{scale}"
                with pyogrio.open_arrow(
                    path,
                    layer=layer,
                    columns=["objekttypnr"],
                    bbox=region.bbox,
                    batch_size=BATCH_SIZE,
                    use_pyarrow=True,
                    IMMUTABLE="YES",
                ) as (meta, reader):
                    if meta["crs"] != "EPSG:3006":
                        raise ValueError(f"{path}:{layer} must use SWEREF 99 TM (EPSG:3006)")
                    geom_column = meta["geometry_name"] or "wkb_geometry"
                    for batch in reader:
                        geom = shapely.from_wkb(
                            batch.column(geom_column).to_numpy(zero_copy_only=False)
                        )
                        clipped = shapely.intersection(shapely.make_valid(geom), extent)
                        for geometry, code in zip(
                            _to_wgs84(clipped, project),
                            batch.column("objekttypnr").to_pylist(),
                            strict=True,
                        ):
                            for polygon in _polygons(geometry):
                                if str(code) not in mapped[tagged_layer]:
                                    raise ValueError(
                                        f"{path}:{layer} has unmapped object type {code}"
                                    )
                                sink.polygon(
                                    [
                                        shapely.get_coordinates(r)
                                        for r in shapely.get_rings(polygon)
                                    ],
                                    {"lm:l": tagged_layer, "lm:t": str(code)},
                                )
                                counts[scale] += 1
            if not counts[scale]:
                raise ValueError(f"{path} has no overview polygons in {region.id}")
    finally:
        sink.close()
    return counts
