# /// script
# requires-python = ">=3.12"
# dependencies = ["rasterio", "numpy"]
# ///
"""SPIKE – most frequent RGB colours in a reference raster (= candidate palette)."""
import sys, numpy as np, rasterio
for p in sys.argv[1:]:
    with rasterio.open(p) as r:
        a = r.read(out_shape=(3, r.height // 2, r.width // 2), resampling=rasterio.enums.Resampling.nearest)
    rgb = (a[0].astype(np.uint32) << 16) | (a[1].astype(np.uint32) << 8) | a[2]
    v, c = np.unique(rgb, return_counts=True)
    o = np.argsort(-c)
    print(f"== {p}: {len(v)} distinct colours; top 25 cover {c[o[:25]].sum()/c.sum():.1%}")
    for i in o[:25]:
        print(f"  #{v[i]:06X}  {c[i]/c.sum():6.2%}")
