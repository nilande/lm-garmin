# Architecture decision records

Format: short MADR. Status is one of *Proposed*, *Accepted*, *Superseded*.
Accepted with the plan on 2026-11-18, except 0005 which waits for the device test.

| # | Decision | Status |
|---|---|---|
| [0001](0001-toolchain-osm-pbf-splitter-mkgmap.md) | Toolchain: GeoPackage → OSM PBF → splitter → mkgmap | Accepted |
| [0002](0002-python-and-java.md) | Python (uv) for our code, Java only for mkgmap/splitter | Accepted |
| [0003](0003-style-independent-intermediate-and-cache.md) | Style-independent `lm:*` tags and staged cache | Accepted |
| [0004](0004-snowmobile-overlay-separate-family.md) | Snowmobile trails as a separate transparent map | Accepted |
| [0005](0005-label-encoding.md) | Label encoding: Unicode if the device accepts it | Proposed – needs device test |
| [0006](0006-verify-by-decoding-img.md) | Verify the built `.img` by decoding it with mkgmap's reader | Accepted |
