# /// script
# requires-python = ">=3.12"
# dependencies = ["pyogrio", "shapely", "pyproj"]
# ///
"""SPIKE – compare skoter line length per category: source GPKG vs decoded .img."""
import json, sys, collections
import pyogrio, shapely
from pyproj import Transformer
from shapely.ops import transform
tr = Transformer.from_crs(4326, 3006, always_xy=True).transform
gpkg, dec = sys.argv[1], sys.argv[2]
m = {"Ja": "0x10e10", "Påbjuden": "0x10e11", "Nej": "0x10e12", "Ingen information": "0x10e13"}
src = collections.Counter()
meta, _, geoms, fields = pyogrio.raw.read(gpkg, layer="ovrig_vag", where="objekttypnr in (1847,1848)")
names = list(meta["fields"])
for g, sk in zip(shapely.from_wkb(geoms), fields[names.index("skoterkorning_tillaten")]):
    src[m[sk]] += g.length
out = collections.Counter()
for l in open(dec):
    f = json.loads(l)
    p = f["properties"]
    if p["kind"] == "line" and p["level"] == 0:
        out[p["type"]] += transform(tr, shapely.geometry.shape(f["geometry"])).length
for k in sorted(m.values()):
    print(f"{k}: src {src[k]:8.0f} m  img {out[k]:8.0f} m  ratio {out[k]/src[k] if src[k] else 0:.3f}")
