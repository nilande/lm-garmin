# 0006 – Verify the built `.img` by decoding it with mkgmap's reader

Status: Accepted · 2026-11-18

## Context
The brief requires that the snowmobile checks run on the **built Garmin map**, not the
intermediate data.

## Options
1. **mkgmap's own `MapReader`** (in the jar we already use) via a tiny Java program
   (`ImgDump.java`) → GeoJSON lines per level.
2. Third-party readers (QMapShack/libgarmin – GUI/C++; GPSMapEdit – Windows, closed;
   Python img readers – unmaintained).

## Decision
Option 1. `java -cp mkgmap.jar ImgDump.java tile.img` (single-file source launch; no build
step). Python consumes the GeoJSON for checks, coverage and rendering.

## Evidence
Spike S4: types, levels, geometry and labels (incl. Unicode) round-trip; decoded lengths
match source within 0.1 % per snowmobile category. Spike S5: coverage on the decoded map
reproduces the brief's 46 % baseline.

## Consequences
- Completeness is checked by **length per type and point counts**, because mkgmap merges
  adjacent line segments.
- Coupled to mkgmap internals; pinned version + integration test catches API changes.
