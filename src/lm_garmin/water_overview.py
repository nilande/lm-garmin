"""Join lake fragments with the same Lantmäteriet water-body identifier."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import pyogrio
import shapely
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon, Polygon

from .region import Bbox

LAKE_TYPE = "2632"
WATER_ID = "vattenytaid"
WHERE_LAKES = f"objekttypnr = {LAKE_TYPE} AND {WATER_ID} IS NOT NULL AND {WATER_ID} <> ''"


def merged_lakes(sources: list[Path], bbox: Bbox) -> dict[str, Polygon | MultiPolygon]:
    """Keep a replacement only when a valid union reduces the number of lake parts."""
    sources = [
        path
        for path in sources
        if {WATER_ID, "objekttypnr"}.issubset(pyogrio.read_info(path, layer="mark")["fields"])
    ]
    counts: Counter[str] = Counter()
    for path in sources:
        _, table = pyogrio.read_arrow(
            path,
            layer="mark",
            bbox=bbox,
            where=WHERE_LAKES,
            columns=[WATER_ID],
            read_geometry=False,
        )
        counts.update(table[WATER_ID].to_pylist())
    repeated = {water_id for water_id, count in counts.items() if count > 1}
    if not repeated:
        return {}

    fragments: dict[str, list[bytes]] = defaultdict(list)
    for path in sources:
        with pyogrio.raw.open_arrow(
            path, layer="mark", bbox=bbox, where=WHERE_LAKES, columns=[WATER_ID], use_pyarrow=True
        ) as (meta, reader):
            for batch in reader:
                ids = batch.column(WATER_ID).to_pylist()
                geom = batch.column(meta["geometry_name"] or "wkb_geometry")
                for index, water_id in enumerate(ids):
                    if water_id in repeated and (wkb := geom[index].as_py()) is not None:
                        fragments[water_id].append(wkb)

    merged = {}
    for water_id, group in fragments.items():
        parts = shapely.get_parts(shapely.from_wkb(group))
        if len(parts) < 2 or not shapely.is_valid(parts).all():
            continue
        try:
            lake = shapely.union_all(parts)
        except GEOSException:
            continue  # Leave the source features active at every scale.
        if (
            isinstance(lake, (Polygon, MultiPolygon))
            and not lake.is_empty
            and lake.is_valid
            and shapely.get_num_geometries(lake) < len(parts)
        ):
            merged[water_id] = lake
    return merged
