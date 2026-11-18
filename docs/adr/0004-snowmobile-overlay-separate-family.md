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

Default delivery: two files (`gmapsupp.img`, `gmapsupp-skoter.img`); a combined
single `gmapsupp.img` with both families is a build option. The final default is chosen
after the device test (spike S6).

## Evidence
Spike S3/S6: overlay compiles with its own TYP, combines with the base map in one gmapsupp,
and decodes with the right types (S4).

## Consequences
- Two family ids to keep stable (proposal: 5730 base, 5731 overlay — to be checked against
  ids used by popular OSM maps).
- A later Skoterleder.org overlay (local only) is a third family with the same mechanism.
