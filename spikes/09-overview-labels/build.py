"""Build a combined Garmin A/B map from matching Topografi 50 and overview tiles."""

import argparse
import csv
import json
import shutil
from collections import Counter
from dataclasses import asdict, fields, replace
from pathlib import Path
from unicodedata import normalize

import osmium
import pyogrio
import shapely
from pyproj import Transformer
from shapely import STRtree
from shapely.ops import nearest_points

from lm_garmin import stylegen, tools
from lm_garmin.build import compile_img
from lm_garmin.convert import ID_STRIDE, THEMES
from lm_garmin.products import PRODUCTS
from lm_garmin.region import parse_bbox
from lm_garmin.verify import decode

RESOLUTIONS = {100: 20, 250: 18}
LAND = "Terrängnamn"
WATER = "Hydrografi"
_TO_WGS84 = Transformer.from_crs(3006, 4326, always_xy=True)


def normalized(name):
    return normalize("NFC", name.strip()).casefold()


def lake_components(folder, bbox):
    path = folder / "mark_sverige.gpkg"
    meta, table = pyogrio.read_arrow(
        path, layer="mark", columns=[], where="objekttypnr = 2632", bbox=bbox, IMMUTABLE="YES"
    )
    return shapely.get_parts(
        shapely.union_all(
            shapely.make_valid(shapely.from_wkb(table[meta["geometry_name"]].to_pylist()))
        )
    )


def labels(folder, bbox):
    path = folder / "text_sverige.gpkg"
    meta, table = pyogrio.read_arrow(
        path,
        layer="textpunkt",
        bbox=bbox,
        IMMUTABLE="YES",
        columns=["textstrang", "textkategori", "textstorleksklass"],
        where="textkategori IN ('Hydrografi', 'Terrängnamn') AND texttyp = 'N'",
    )
    for row in table.to_pylist():
        name = normalize("NFC", (row["textstrang"] or "").strip())
        if name:
            yield (
                name,
                row["textkategori"],
                int(row["textstorleksklass"] or 0),
                shapely.from_wkb(row[meta["geometry_name"]]),
            )


def select_labels(folders, bbox):
    medium = list(labels(folders[100], bbox))
    important_terrain = {}
    for name, category, size, point in medium:
        if category == LAND and size >= 4:
            important_terrain.setdefault(normalized(name), []).append(point)

    medium_lakes = {}
    for scale, folder in folders.items():
        lakes = lake_components(folder, bbox)
        tree = STRtree(lakes)
        water_labels = {}
        terrain_labels = {}
        entries = medium if scale == 100 else labels(folder, bbox)
        for name, category, size, point in sorted(
            entries, key=lambda row: (-row[2], normalized(row[0]), row[3].x, row[3].y)
        ):
            key = normalized(name)
            if category == WATER:
                if size < (3 if scale == 100 else 2):
                    continue
                hits = tree.query(point, predicate="intersects")
                if len(hits):
                    lake_index = max(hits, key=lambda index: lakes[index].area)
                elif scale == 250 and key in medium_lakes:
                    lake_index = tree.nearest(point)
                    if lake_index is None:
                        continue
                    lake = lakes[lake_index]
                    if lake.distance(point) > 100 or not any(
                        lake.intersects(other) for other in medium_lakes[key]
                    ):
                        continue
                    interior = lake.buffer(-15)
                    point = (
                        nearest_points(point, interior)[1]
                        if not interior.is_empty
                        else lake.representative_point()
                    )
                else:
                    continue
                lake = lakes[lake_index]
                if scale == 250 and lake.area < 1_000_000:
                    continue
                distance = point.distance(lake.representative_point())
                rank = (-size, distance)
                current = water_labels.get((key, lake_index))
                if current is None or rank < current[0]:
                    water_labels[key, lake_index] = (rank, name, point)
            elif size >= 4 or (
                scale == 250
                and size >= 2
                and any(point.distance(other) <= 2000 for other in important_terrain.get(key, ()))
            ):
                placements = terrain_labels.setdefault(key, [])
                if not any(point.distance(other) <= 500 for _, other in placements):
                    placements.append((name, point))

        if scale == 100:
            for key, lake_index in water_labels:
                medium_lakes.setdefault(key, []).append(lakes[lake_index])
        yield scale, WATER, [(name, point) for _, name, point in water_labels.values()]
        yield scale, LAND, [item for placements in terrain_labels.values() for item in placements]


def attach_labels(source, target, label_groups):
    data = osmium.FileProcessor(source)
    # Reserve an id range beyond the overview polygon nodes written by lm_garmin.overview.
    ids = iter(range((len(THEMES) + 2) * ID_STRIDE, (len(THEMES) + 3) * ID_STRIDE))
    new_nodes = [
        osmium.osm.mutable.Node(
            id=next(ids),
            location=_TO_WGS84.transform(point.x, point.y),
            tags={"lm:l": f"overview_name{scale}", "name": name},
        )
        for scale, _, rows in label_groups
        for name, point in rows
    ]
    with osmium.SimpleWriter(target, header=data.header, overwrite=True) as writer:
        for obj in data:
            if new_nodes and not obj.is_node():
                for node in new_nodes:
                    writer.add_node(node)
                new_nodes.clear()
            writer.add(obj)
        for node in new_nodes:
            writer.add_node(node)


def write_style(path, product, candidate):
    rules = stylegen.load(product.style_dir / "mapping.csv")
    path.mkdir(parents=True, exist_ok=True)
    if candidate:
        marker = next(i for i, rule in enumerate(rules) if rule.layer == "textpunkt")
        template = next(r for r in rules if r.layer == "textpunkt" and r.type == "0x2800")
        original = replace(
            template,
            condition="lm:textkategori=Hydrografi | lm:textkategori=Terrängnamn",
            resolution="21",
        )
        rules.insert(marker, original)
        rules.extend(
            replace(
                template, layer=f"overview_name{scale}", condition="", resolution=f"{res}-{res}"
            )
            for scale, res in RESOLUTIONS.items()
        )
    with (path / "mapping.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[field.name for field in fields(stylegen.Rule)])
        writer.writeheader()
        writer.writerows(asdict(rule) for rule in rules)
    for relative, text in stylegen.generated_files(
        path,
        product.family_id,
        product.levels,
        overview_resolutions=tuple(RESOLUTIONS.values()) if candidate else (),
    ).items():
        dest = path / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


def map_points(img):
    levels = {level: Counter() for level in range(7)}
    for feature in decode(img):
        props = feature["properties"]
        if props["kind"] == "point":
            key = props["type"], props.get("label"), tuple(feature["geometry"]["coordinates"])
            levels[props["level"]][key] += 1
    return levels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topo100-dir", type=Path, required=True)
    parser.add_argument("--topo250-dir", type=Path, required=True)
    parser.add_argument(
        "--area",
        nargs=4,
        action="append",
        required=True,
        metavar=("NAME", "SWEREF_BBOX", "REFERENCE_PBF", "CANDIDATE_PBF"),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    java = tools.find_java()
    if not java:
        parser.error("Java is required")
    outputs = {}
    base = PRODUCTS["topo50"]
    folders = {100: args.topo100_dir, 250: args.topo250_dir}
    inventory = {}
    for area, bbox, ref, candidate in args.area:
        if str(osmium.FileProcessor(ref).header.box()) != str(
            osmium.FileProcessor(candidate).header.box()
        ):
            parser.error(f"{area}: tile bounds differ")
        inventory[area] = list(select_labels(folders, parse_bbox(bbox)))
    for key, name, family, is_candidate in (
        ("referens", "LM Test referens", 5770, False),
        ("oversikt", "LM Test oversikt", 5771, True),
    ):
        work = args.out / "work" / key
        tiles = []
        style = work / "topo50"
        product = replace(base, name=name, family_id=family, mapid_base=family * 10_000 + 1)
        write_style(style, product, is_candidate)
        for index, (area, _, ref, candidate) in enumerate(args.area):
            tile = work / f"{product.mapid_base + index}.osm.pbf"
            if is_candidate:
                attach_labels(candidate, tile, inventory[area])
            else:
                shutil.copyfile(ref, tile)
            tiles.append(tile)
        compile_img(java, tiles, style, work / "img", product, jobs=2, java_mem="4g")
        outputs[key] = args.out / f"lm-test-{key}.img"
        shutil.copyfile(work / "img" / "gmapsupp.img", outputs[key])
    reference, candidate = (map_points(outputs[key]) for key in ("referens", "oversikt"))
    for level in (0, 1, 2, 3, 6):
        if reference[level] != candidate[level]:
            raise ValueError(f"Point content differs at level {level}")
    result = {
        "same_point_content_at_levels": [0, 1, 2, 3, 6],
        "selected": {
            area: {
                f"{scale} {category}": sorted(name for name, _ in rows)
                for scale, category, rows in groups
            }
            for area, groups in inventory.items()
        },
        "points_per_level": {
            key: {level: counts.total() for level, counts in levels.items()}
            for key, levels in (("reference", reference), ("candidate", candidate))
        },
    }
    (args.out / "comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    for target in outputs.values():
        print(target)


if __name__ == "__main__":
    main()
