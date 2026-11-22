"""SPIKE – label size kit for the Montana 700 (#71): which point types, line types and TYP
settings change label size, weight or colour? One small map near Täby; show it alone.

Column A: city point types 0x0100–0x1100 (no TYP). Column B: label points 0x2800–0x2803 with
TYP FontStyle default/Small/Normal/Large, and 0x2804 with DayCustomColor red. Column C: road
line types without TYP. Column D: road types 0x07–0x0a with TYP FontStyle and colour, and
non-road line types (streams, rivers, boundaries) with their default label.
"""

import subprocess
import sys
from pathlib import Path

from pyproj import Transformer

HERE = Path(__file__).parent
OUT = HERE / "out"
JAVA = "/opt/homebrew/opt/openjdk/bin/java"
MKGMAP = Path.home() / ".cache/lm-garmin/tools/mkgmap-r4924/mkgmap.jar"
E0, N0, STEP = 669000, 6594000, 100  # top-left of the grid (SWEREF 99 TM), 100 m rows
tr = Transformer.from_crs(3006, 4326, always_xy=True)

cities = [f"0x{t:02x}00" for t in range(0x01, 0x12)]
labels = [
    ("0x2800", "default"),
    ("0x2801", "SmallFont"),
    ("0x2802", "NormalFont"),
    ("0x2803", "LargeFont"),
    ("0x2804", "red colour"),
]
roads = ["0x01", "0x02", "0x03", "0x04", "0x05", "0x06", "0x0b", "0x0c", "0x10", "0x11", "0x13"]
styled = [
    ("0x07", "SmallFont"),
    ("0x08", "NormalFont"),
    ("0x09", "LargeFont"),
    ("0x0a", "Small red"),
]
other = [("0x18", "stream"), ("0x1f", "river"), ("0x1c", "boundary"), ("0x14", "railway")]

nodes, ways, rules_p, rules_l = [], [], [], []
nid = 1


def node(e, n, tags=None):
    global nid
    lon, lat = tr.transform(e, n)
    t = "".join(f'<tag k="{k}" v="{v}"/>' for k, v in (tags or {}).items())
    nodes.append(f'<node id="{nid}" lat="{lat:.7f}" lon="{lon:.7f}" version="1">{t}</node>')
    nid += 1
    return nid - 1


def point(col, row, typ, name):
    node(E0 + col * 700, N0 - row * STEP, {"diag": typ, "name": name})


def line(col, row, typ, name):
    a = node(E0 + col * 700, N0 - row * STEP)
    b = node(E0 + col * 700 + 450, N0 - row * STEP)
    tags = f'<tag k="diag" v="{typ}"/><tag k="name" v="{name}"/>'
    ways.append(f'<way id="{len(ways) + 1}" version="1"><nd ref="{a}"/><nd ref="{b}"/>{tags}</way>')


for i, t in enumerate(cities):
    point(0, i, t, f"{t} Ella gård")
    rules_p.append(f"diag={t} [{t} resolution 20]")
for i, (t, what) in enumerate(labels):
    point(1, i, t, f"{t} {what}")
    rules_p.append(f"diag={t} [{t} resolution 20]")
for i, t in enumerate(roads):
    line(2, i, t, f"Väg {t} Ellagatan")
    rules_l.append(f"diag={t} [{t} resolution 20]")
for i, (t, what) in enumerate(styled + other):
    line(3, i, t, f"{t} {what} Ellagatan")
    rules_l.append(f"diag={t} [{t} resolution 20]")

OUT.mkdir(exist_ok=True)
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
(style / "info").write_text("version 0\nsummary: label size kit\n")
(style / "options").write_text("levels = 0:24, 1:20\n")
(style / "points").write_text("name=* { name '${name}' }\n" + "\n".join(rules_p) + "\n")
(style / "lines").write_text("name=* { name '${name}' }\n" + "\n".join(rules_l) + "\n")
(style / "polygons").write_text("")
(style / "relations").write_text("")

dot = 'Xpm="5 5 1 1"\n"a c #000000"\n' + '"aaaaa"\n' * 5
typ = ["[_id]\nFID=5759\nProductCode=1\nCodePage=65001\n[end]\n"]
fonts = {"0x2801": "SmallFont", "0x2802": "NormalFont", "0x2803": "LargeFont"}
for t, _ in labels:
    extra = f"FontStyle={fonts[t]}\n" if t in fonts else ""
    if t == "0x2804":
        extra = "DayCustomColor=#FF0000\n"
    typ.append(f"[_point]\nType={t}\nString1=0x04,{t}\n{extra}{dot}[end]\n")
line_style = {
    "0x07": "FontStyle=SmallFont\n",
    "0x08": "FontStyle=NormalFont\n",
    "0x09": "FontStyle=LargeFont\n",
    "0x0a": "FontStyle=SmallFont\nDayCustomColor=#FF0000\n",
}
for t, extra in line_style.items():
    typ.append(f'[_line]\nType={t}\nString1=0x04,{t}\n{extra}LineWidth=3\nXpm="0 0 1 0"\n"a c #8C8C8C"\n[end]\n')
(OUT / "kit-typ.txt").write_text("\n".join(typ), encoding="utf-8")

r = subprocess.run(
    [JAVA, "-jar", str(MKGMAP), f"--output-dir={OUT}", f"--style-file={style}",
     "--family-id=5759", "--product-id=1", "--mapname=57590001",
     "--family-name=LM Label kit", "--series-name=LM Label kit", "--description=LM Label kit",
     "--unicode", "--lower-case", "--gmapsupp", str(osm), str(OUT / "kit-typ.txt")],
    capture_output=True, text=True,
)
print(r.stdout[-2000:], r.stderr[-2000:])
if r.returncode:
    sys.exit(r.returncode)
(OUT / "gmapsupp.img").replace(OUT / "lm-labelkit.img")
print("wrote", OUT / "lm-labelkit.img")
