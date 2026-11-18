# 0002 – Python (uv) for our code, Java only for mkgmap/splitter

Status: Accepted · 2026-11-18

## Context
We need: fast GeoPackage reading with spatial filters, reprojection, light geometry work
(dissolve, simplify, multipolygons), PBF writing, orchestration, tests. mkgmap and splitter
require Java regardless.

## Options
- **Python 3.12+** with pyogrio (GDAL, Arrow), shapely 2, pyproj, pyosmium; uv for envs.
- **Java** for everything (same runtime as mkgmap; GeoTools; heavier, fewer geo contributors).
- **Rust/Go** (fast, single binary; GDAL bindings and OSM writers less mature; higher bar for
  contributors).

## Decision
Python for the tool; Java only as external processes (mkgmap, splitter) plus a one-file
`ImgDump.java` for verification that runs on the mkgmap jar.

## Rationale
- The heavy lifting is in GDAL (C++), GEOS (C++), PROJ (C++), libosmium (C++) and mkgmap —
  Python only orchestrates vectorised calls. Spike S7: converting 50×50 km (all layers) took
  6 s even with a naive XML writer; mkgmap/splitter dominate.
- Largest contributor pool for GIS work; uv gives reproducible, fast environments.
- Measure before optimising: if S1 ever dominates, the hot loop can move to a Rust extension
  without changing the architecture.

## Dependencies
Runtime: Python ≥ 3.12, GDAL ≥ 3.8 (via pyogrio wheels), shapely ≥ 2, pyproj, pyosmium,
numpy; Java ≥ 17 (tested on 27). Dev: ruff, pytest, pytest-xdist. Pinned via `uv.lock`.
