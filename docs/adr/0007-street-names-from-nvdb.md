# 0007 – Street names from Trafikverket NVDB

Status: **Proposed** · 2026-11-20 (issue #55; waiting for the matching test)

## Context
Topografi 50 has no street names (`vaglinje.gatunamn` is empty). Users in towns need named
streets. The evaluation is in [docs/street-names.md](../street-names.md).

## Options
1. **NVDB from Trafikverket's Lastkajen.** CC0, the authoritative source of the names, and
   the same road network Topografi 50 is generalised from. Needs a free account and
   geometric matching.
2. **Topografi 10 from Lantmäteriet.** It has the NVDB names in the same `vaglinje` schema, so
   matching would be simpler. Licence CC BY 4.0 with terms for data containing personal data
   (the user becomes data controller, with purpose limits and audits). This is not suitable as
   a default for an open tool that others run and share maps from.
3. **OpenStreetMap.** Good coverage, but ODbL share-alike. Possible as a local-only optional
   source, like the OSM snowmobile supplement.

## Decision (proposed)
Use **NVDB** as an optional input (`--nvdb-dir`, like `--topo250-dir`), matched to
Topografi 50 roads by buffer, bearing and overlap. Do not use Topografi 10. OSM names may be
added later as a local-only fallback.

## To be confirmed by the matching test
Coverage ≥ 90 % of town street length in Täby, ≤ 2 wrong names per 100 sampled segments,
and acceptable runtime. If matching to Topografi 50 geometry is not good enough, the
alternative is to draw town streets from NVDB geometry at the most detailed levels.

## Consequences
- All inputs stay CC0. Built maps keep "© Lantmäteriet" and add "Trafikverket (NVDB)" as source.
- New tag (tag schema bump), style rules for road names, a small CC0 NVDB fixture in
  `tests/data`.
- One more delivery for users to download (Lastkajen account).
