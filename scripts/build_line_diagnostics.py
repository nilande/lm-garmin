"""Build labelled synthetic line samples near Ensta, Täby, for Montana screenshots."""

from __future__ import annotations

import argparse
import csv
import shutil
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
from pyproj import Transformer

from lm_garmin import stylegen, tools
from lm_garmin.build import compile_img
from lm_garmin.convert import OsmSink
from lm_garmin.products import PRODUCTS, Product

CENTER = (673560, 6594595)  # Ensta
PRODUCT = Product(
    key="line-diagnostics",
    style="line-diagnostics",
    family_id=5758,
    mapid_base=57580001,
    name="Täby syntetiska testlinjer",
    levels=PRODUCTS["skoter-osm"].levels,
    transparent=True,
    draw_priority=31,
    output="taby-testlinjer.img",
    copyright="Synthetic Garmin line samples",
)


def samples() -> list[stylegen.Rule]:
    osm = {r.type: r for r in stylegen.load(PRODUCTS["skoter-osm"].style_dir / "mapping.csv")}
    lm = {r.type: r for r in stylegen.load(PRODUCTS["skoter"].style_dir / "mapping.csv")}
    designated = osm["0x10e0f"]
    return [
        replace(designated, type="0x10c00"),  # Previous code, same bitmap as the next row.
        designated,
        osm["0x10c01"],
        osm["0x10c02"],
        lm["0x10e14"],
        lm["0x10e16"],
        replace(designated, type="0x04", colour="#AE65BE", pattern="solid", description="Testväg"),
    ]


def build(out: Path) -> None:
    java = tools.find_java()
    if not java:
        raise SystemExit("Java 17+ is required to build the diagnostic overlay.")
    out.mkdir(parents=True, exist_ok=True)
    lines = samples()
    project = Transformer.from_crs(3006, 4326, always_xy=True)
    east, north = CENTER
    extent = (east - 500, north - 500, east + 500, north + 500)

    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        style = work / PRODUCT.style
        style.mkdir()
        pbf = work / f"{PRODUCT.mapid_base}.osm.pbf"
        sink = OsmSink(pbf, 1, project.transform_bounds(*extent))
        with (style / "mapping.csv").open("w", encoding="utf-8", newline="") as file:
            rules = csv.DictWriter(file, asdict(lines[0]).keys())
            rules.writeheader()
            rules.writerow(
                {
                    "kind": "point",
                    "layer": "diagnostic_label",
                    "type": "0x2800",
                    "resolution": "18",
                    "name": "${name}",
                    "pattern": "none",
                }
            )
            for index, line in enumerate(lines):
                row = str(index + 1)
                rules.writerow(
                    asdict(
                        replace(
                            line,
                            layer="diagnostic_line",
                            t=row,
                            condition="",
                            resolution="18",
                            name="",
                        )
                    )
                )
                y = north + (len(lines) // 2 - index) * 125
                x, lat = project.transform([east - 300, east + 300], [y, y])
                sink.way(np.column_stack((x, lat)), {"lm:l": "diagnostic_line", "lm:t": row})
                label_x = east - 365 if index % 2 == 0 else east + 365
                lon, latitude = project.transform(label_x, y)
                sink.point(
                    lon, latitude, {"lm:l": "diagnostic_label", "name": f"{row} {line.type}"}
                )
        sink.close()
        stylegen.generate(style, PRODUCT.family_id, PRODUCT.levels)
        compiled = work / "compiled"
        compile_img(java, [pbf], style, compiled, PRODUCT, jobs=1, java_mem="1g")
        shutil.copyfile(compiled / "gmapsupp.img", out / PRODUCT.filename)

    lon, latitude = project.transform(*CENTER)
    print(f"{out / PRODUCT.filename} – map centre {latitude:.5f}, {lon:.5f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("dist/line-diagnostics"))
    build(parser.parse_args().out)
