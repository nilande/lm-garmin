# 0003 – Style-independent intermediate (`lm:*` tags) and staged cache

Status: Accepted · 2026-11-18

## Context
The brief requires incremental builds: a style change must not re-process all data.
Lantmäteriet's data is ~15 GB; a full conversion takes tens of minutes.

## Decision
- The converter (S1) writes **only Lantmäteriet semantics** as tags: `lm:l` (table),
  `lm:t` (objekttypnr), selected attributes (`lm:sk`, `lm:idx`, `ele`, `name`, `ref`, text
  layout tags). No Garmin types, no zoom levels, no colours.
- All presentation lives in `styles/<name>/` (mkgmap style rules + TYP text).
- Stages S0–S3 write to a cache keyed by a hash of their inputs (data manifest, region,
  converter/tag-schema version, tool versions, and — for S3 only — the style directory).
- Geometry pre-processing that is presentation-*neutral* (overview dissolves, multi-part
  names) is part of S1 and versioned with it.

## Consequences
- Style-only rebuild = S3 only (mkgmap: seconds per 50 km tile).
- Alternative styles are cheap: same S1/S2 output.
- The tag schema is a public contract → documented in `docs/tag-schema.md` and unit-tested.
