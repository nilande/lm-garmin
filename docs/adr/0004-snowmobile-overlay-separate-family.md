# 0004 – Snowmobile trails as a separate transparent map

Status: Accepted · 2026-11-18

## Context
The user wants Lantmäteriet's snowmobile information (`ovrig_vag` 1847/1848 with
`skoterkorning_tillaten`, points 1836) clearly visible and switchable on the device.

## Options
1. Draw it in the base map only. Cannot be switched off; restyling needs a full rebuild.
2. **Separate map product** (own family id, `--transparent`, high draw priority, own TYP).
   Can be enabled/disabled in the device's map setup.

## Decision
Option 2. The base map still shows 1847/1848 as "marked winter trail" (like Karta 1:50 000),
the overlay adds the snowmobile status styling on top.

Default delivery uses `lm-topo50.img` and `lm-skoter.img`, which can be toggled
independently on the Montana. An optional single-file bundle is tracked in
[#51](https://github.com/nilande/lm-garmin/issues/51).

## Evidence
Spike S3/S6: overlay compiles with its own TYP, combines with the base map in one gmapsupp,
and decodes with the right types (S4).

## Consequences
- Keep the production family IDs stable (5750 base, 5751 Lantmäteriet overlay).
- The optional supplement reads a local OpenStreetMap extract directly and uses its
  own family and line style. A locally held Skoterleder.org GPX is used only for an
  optional coverage comparison.
