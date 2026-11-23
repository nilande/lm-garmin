"""SPIKE – which device label setting governs which label (#81)?

*Map Setup › Advanced Setup* has *Text Size* and *Zoom Levels* for Map Points, Street Label
and Land Cover. Street Label is known (#82). This kit puts one example of every label kind
our maps use, plus common POIs and named areas, in six columns just east of Täby
(outside the Täby municipality dev map, so it can stay on). No TYP file: device defaults.

A city points 0x0100–0x1100 (place names)
B label points 0x2800–0x2806 (our map texts)
C geographic POIs alone, no label point next to them (0x6500 water, 0x650d lake,
  0x6616 summit, 0x6614 rock, 0x6608 crater …) – the searchable lake/terrain points
D common POIs (restaurant, landmark, fuel, building, church, parking)
E named polygons (lake 0x3c, forest 0x50, park 0x17, wetland 0x51, glacier 0x4d)
F named lines (contour 0x20, stream 0x18, river 0x1f, trail 0x16)
"""

import subprocess
import sys
from pathlib import Path

from pyproj import Transformer

HERE = Path(__file__).parent
OUT = HERE / "out" / "categories"
JAVA = "/opt/homebrew/opt/openjdk/bin/java"
MKGMAP = Path.home() / ".cache/lm-garmin/tools/mkgmap-r4924/mkgmap.jar"
E0, N0, STEP, COL = 681500, 6596000, 120, 700  # top-left (SWEREF 99 TM), row and column step
tr = Transformer.from_crs(3006, 4326, always_xy=True)

COLUMNS = {
    "A": ("point", [(f"0x{t:02x}00", "ort") for t in (0x01, 0x04, 0x08, 0x0B, 0x0D, 0x0E, 0x11)]),
    "B": ("point", [(f"0x280{i}", "etikett") for i in range(7)]),
    "C": (
        "point",
        [
            ("0x6500", "vatten"),
            ("0x650d", "sjö"),
            ("0x6616", "topp"),
            ("0x6614", "sten"),
            ("0x6608", "krater"),
            ("0x6604", "strand"),
            ("0x6600", "terräng"),
        ],
    ),
    "D": (
        "point",
        [
            ("0x2a00", "restaurang"),
            ("0x2c04", "landmärke"),
            ("0x2f01", "bensin"),
            ("0x6402", "byggnad"),
            ("0x6404", "kyrka"),
            ("0x2f0b", "parkering"),
        ],
    ),
    "E": (
        "polygon",
        [
            ("0x3c", "sjöyta"),
            ("0x50", "skog"),
            ("0x17", "park"),
            ("0x51", "våtmark"),
            ("0x4d", "glaciär"),
        ],
    ),
    "F": (
        "line",
        [("0x20", "höjdkurva"), ("0x18", "bäck"), ("0x1f", "älv"), ("0x16", "led")],
    ),
}

nodes, ways = [], []
rules = {"point": [], "line": [], "polygon": []}
nid = 1


def node(e, n, tags=None):
    global nid
    lon, lat = tr.transform(e, n)
    t = "".join(f'<tag k="{k}" v="{v}"/>' for k, v in (tags or {}).items())
    nodes.append(f'<node id="{nid}" lat="{lat:.7f}" lon="{lon:.7f}" version="1">{t}</node>')
    nid += 1
    return nid - 1


def way(coords, tags):
    refs = [node(e, n) for e, n in coords]
    if tags.get("area"):
        refs.append(refs[0])
    nd = "".join(f'<nd ref="{r}"/>' for r in refs)
    t = "".join(f'<tag k="{k}" v="{v}"/>' for k, v in tags.items())
    ways.append(f'<way id="{len(ways) + 1}" version="1">{nd}{t}</way>')


for c, (col, (kind, items)) in enumerate(COLUMNS.items()):
    e = E0 + c * COL
    for r, (typ, word) in enumerate(items):
        n = N0 - r * STEP
        name = f"{col}{r + 1} {typ} {word}"
        if kind == "point":
            node(e, n, {"diag": typ, "name": name})
        elif kind == "line":
            way([(e, n), (e + 450, n)], {"diag": typ, "name": name})
        else:
            way(
                [(e, n + 40), (e + 450, n + 40), (e + 450, n - 40), (e, n - 40)],
                {"diag": typ, "name": name, "area": "yes"},
            )
        rules[kind].append(f"diag={typ} [{typ} resolution 20]")

OUT.mkdir(parents=True, exist_ok=True)
osm = OUT / "kit.osm"
osm.write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6">\n'
    + "\n".join(nodes + ways)
    + "\n</osm>\n",
    encoding="utf-8",
)
style = OUT / "style"
style.mkdir(exist_ok=True)
(style / "version").write_text("0\n")
(style / "info").write_text("version 0\nsummary: label category kit\n")
(style / "options").write_text("levels = 0:24, 1:20\n")
for kind, file in (("point", "points"), ("line", "lines"), ("polygon", "polygons")):
    (style / file).write_text("name=* { name '${name}' }\n" + "\n".join(rules[kind]) + "\n")
(style / "relations").write_text("")

r = subprocess.run(
    [
        JAVA,
        "-jar",
        str(MKGMAP),
        f"--output-dir={OUT}",
        f"--style-file={style}",
        "--family-id=5758",
        "--product-id=1",
        "--mapname=57580001",
        "--family-name=LM Label categories",
        "--series-name=LM Label categories",
        "--description=LM Label categories",
        "--unicode",
        "--lower-case",
        "--gmapsupp",
        str(osm),
    ],
    capture_output=True,
    text=True,
)
print(r.stdout[-2000:], r.stderr[-2000:])
if r.returncode:
    sys.exit(r.returncode)
(OUT / "gmapsupp.img").replace(OUT / "lm-labelcat.img")
print("wrote", OUT / "lm-labelcat.img")
