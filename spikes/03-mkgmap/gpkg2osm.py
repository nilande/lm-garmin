# /// script
# requires-python = ">=3.12"
# dependencies = ["pyogrio>=0.10", "shapely>=2.0", "pyproj>=3.6", "numpy"]
# ///
"""SPIKE – not production code.

Convert a (clipped) Topografi 50 GeoPackage to OSM XML with synthetic
tags that a mkgmap style can match on:

  lm:l   = source table       lm:t = objekttypnr
  lm:sk  = skoterkorning_tillaten (ovrig_vag only)
  name   = textstrang / karttext / gatunamn
  ele    = hojdvarde
  lm:idx = 'yes' for stodkurva=Ja

Usage: uv run gpkg2osm.py in.gpkg out.osm [--only skoter]
"""
import sys
import time
from xml.sax.saxutils import quoteattr

import numpy as np
import pyogrio
import shapely
from pyproj import Transformer

TR = Transformer.from_crs(3006, 4326, always_xy=True)
SKOTER = {("ovrig_vag", 1847), ("ovrig_vag", 1848), ("ledintressepunkt_fjall", 1836)}


class Writer:
    def __init__(self, f):
        self.f = f
        self.nid = 0
        self.wid = 0
        self.rid = 0
        self.ways = []  # buffered: nodes must come first in OSM XML
        self.rels = []
        self.counts = {"node": 0, "way": 0, "relation": 0}

    def tags(self, t):
        return "".join(f"<tag k={quoteattr(k)} v={quoteattr(str(v))}/>" for k, v in t.items())

    def node(self, lon, lat, tags=None):
        self.nid += 1
        body = self.tags(tags) if tags else ""
        self.f.write(f'<node id="{self.nid}" lat="{lat:.7f}" lon="{lon:.7f}" version="1">{body}</node>\n')
        self.counts["node"] += 1
        return self.nid

    def way(self, coords, tags, closed=False):
        lon, lat = TR.transform(coords[:, 0], coords[:, 1])
        ids = [self.node(x, y) for x, y in zip(lon, lat)]
        if closed and ids[0] != ids[-1]:
            ids.append(ids[0])
        elif closed:
            ids[-1] = ids[0]
        self.wid += 1
        nds = "".join(f'<nd ref="{i}"/>' for i in ids)
        self.ways.append(f'<way id="{self.wid}" version="1">{nds}{self.tags(tags)}</way>\n')
        self.counts["way"] += 1
        return self.wid

    def polygon(self, poly, tags):
        ext = np.asarray(poly.exterior.coords)
        if not poly.interiors:
            self.way(ext, tags, closed=True)
            return
        outer = self.way(ext, {}, closed=True)
        inners = [self.way(np.asarray(r.coords), {}, closed=True) for r in poly.interiors]
        self.rid += 1
        mem = f'<member type="way" ref="{outer}" role="outer"/>' + "".join(
            f'<member type="way" ref="{i}" role="inner"/>' for i in inners
        )
        t = dict(tags, type="multipolygon")
        self.rels.append(f'<relation id="{self.rid}" version="1">{mem}{self.tags(t)}</relation>\n')
        self.counts["relation"] += 1


def feature_tags(layer, props):
    t = {"lm:l": layer}
    if "objekttypnr" in props and props["objekttypnr"] is not None:
        t["lm:t"] = int(props["objekttypnr"])
    for src in ("textstrang", "karttext", "gatunamn"):
        v = props.get(src)
        if v:
            t["name"] = v
            break
    if props.get("hojdvarde") is not None:
        t["ele"] = props["hojdvarde"]
    if props.get("stodkurva") == "Ja":
        t["lm:idx"] = "yes"
    if props.get("skoterkorning_tillaten"):
        t["lm:sk"] = props["skoterkorning_tillaten"]
    if props.get("textstorleksklass"):
        t["lm:size"] = props["textstorleksklass"]
    if props.get("textkategori"):
        t["lm:cat"] = props["textkategori"]
    if props.get("vardvagnummer"):
        t["ref"] = props["vardvagnummer"]
    return t


def main():
    src, dst = sys.argv[1], sys.argv[2]
    only_skoter = "--only" in sys.argv and sys.argv[sys.argv.index("--only") + 1] == "skoter"
    t0 = time.time()
    with open(dst, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6" generator="lm-garmin-spike">\n')
        w = Writer(f)
        for layer, _ in pyogrio.list_layers(src):
            meta, _fids, geoms, fields = pyogrio.raw.read(src, layer=layer)
            names = list(meta["fields"])
            if geoms is None:
                continue
            gs = shapely.from_wkb(geoms)
            for i, g in enumerate(gs):
                if g is None or g.is_empty:
                    continue
                props = {n: fields[j][i] for j, n in enumerate(names)}
                tags = feature_tags(layer, props)
                if only_skoter and (layer, tags.get("lm:t")) not in SKOTER:
                    continue
                for part in getattr(g, "geoms", [g]):
                    gt = part.geom_type
                    if gt == "Point":
                        lon, lat = TR.transform(part.x, part.y)
                        w.node(lon, lat, tags)
                    elif gt == "LineString":
                        w.way(np.asarray(part.coords), tags)
                    elif gt == "Polygon":
                        w.polygon(part, tags)
        f.writelines(w.ways)
        f.writelines(w.rels)
        f.write("</osm>\n")
    print(f"{dst}: {w.counts} in {time.time() - t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
