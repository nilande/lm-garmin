# 0007 – Street names from Trafikverket NVDB

Status: **Proposed for acceptance** · 2026-11-20 (issue #55; matching test done – merging this ADR accepts it)

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

## Evidence (matching test, Täby)
NVDB delivery 2026-11-17 confirmed CC0. Matching Topografi 50 roads to
`NVDB_DK_O_20_Gatunamn` named **90.0 %** of town-street length (97 % of main and large local
streets) in 0.5 s for a 15 × 15 km area. The result is insensitive to the buffer size. The
remaining 10 % is unnamed in NVDB within 15 m, or a name changes along a segment. See
[street-names.md](../street-names.md#matching-test--result-täby-dev-area). The error rate
still needs an automated check in the implementation; the visual sample was too small.

## Consequences
- All inputs stay CC0. Built maps keep "© Lantmäteriet" and add "Trafikverket (NVDB)" as source.
- New tag (tag schema bump), style rules for road names, a small CC0 NVDB fixture in
  `tests/data`.
- One more delivery for users to download (Lastkajen account).
