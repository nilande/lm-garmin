# 0001 – Toolchain: GeoPackage → OSM PBF → splitter → mkgmap

Status: Accepted · 2026-11-18

## Context
Garmin `.img` is an undocumented vector format. The only maintained open-source compiler is
**mkgmap** (GPL-2, Java). It reads OSM data (XML/PBF/o5m) and, with limitations, Polish
format (`.mp`). Large inputs must be cut into tiles first; **splitter** does that for OSM input.

## Options
1. **OSM PBF + splitter + mkgmap** (brief's proposal). Mainstream path used by every
   OSM-based Garmin map; style rules and TYP are text; splitter gives stable tiles.
2. **Polish `.mp` + mkgmap.** mkgmap can read `.mp`, but splitter cannot split it – we would
   have to tile ourselves; the `.mp` path in mkgmap is less used and less tested; styling is
   expressed in the `.mp` file, i.e. tied to conversion (breaks ADR-0003).
3. **Polish `.mp` + cGPSmapper.** Closed source, unmaintained.
4. **Write `.img` ourselves.** Huge effort, reverse-engineered format, no gain.
5. **ogr2osm** as the converter. Generic, slower, one more dependency; our writer is ~150 lines
   for exactly the tags we need.

## Decision
Option 1, with our own GPKG→PBF converter (ADR-0002).

## Evidence
Spike S3: three test areas + TYP → `gmapsupp.img` in 0.8 s; overlay as second family works.
Spike S7: 50×50 km Stockholm: convert 6 s, split 11 s, compile 5 s.

## Consequences
- OSM ids must be positive and ascending (splitter); one id range per theme.
- We depend on two Java tools; versions are pinned and checksummed.
- OSM tags are only a transport format; we do not try to mimic OSM semantics.
