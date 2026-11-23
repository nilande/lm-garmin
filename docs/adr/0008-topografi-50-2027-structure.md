# 0008 – Support the current and the 2027.05 Topografi 50 structure side by side

Status: **Accepted** · 2026-11-23 (issue #56)

## Context
Lantmäteriet changes the structure of *Topografi 50 Nedladdning, vektor* on **2027-05-04**
(version 2027.05). The changes that matter here, from the product description and the test
data ([data-inventory.md](../data-inventory.md#structure-change-202705-from-2027-05-04-issue-56)):

- a new layer `cykelvaglinje` (theme `kommunikation`) takes over cycle paths (1623) from
  `ovrig_vag`;
- `hojdpunkt` 2412 is renamed *Planpunkt* (number unchanged);
- the test data's `vaglinje` has no `vardvagnummer`, although the description keeps it.

Until the switch, and for anyone who keeps an older delivery, both structures must build.

## Options
1. **Detect the version and switch** (from `uttag.json`, the GeoPackage metadata or the layer
   list), with one style per structure.
2. **One converter and style that accept both**: read whatever layers and columns exist, keep
   rules for both places of a feature, and report what the style expects but the delivery
   lacks.
3. **A clean switch on 2027-05-04**: drop support for the current structure.

## Decision
Option 2. The differences are additive (a new layer, a moved object type, a renamed type), so
one style covers both: `cykelvaglinje` is in `THEME_LAYERS` (appended, so OSM id ranges stay)
and drawn like `ovrig_vag` 1623, whose rule stays for current deliveries. Tag meanings do not
change, so `SCHEMA_VERSION` stays 5. `build` warns and records `missing_columns` when a style
tag has no source column (#75). No version detection is needed, and the build report already
records the source files.

CI builds `tatort_659_67_00_2027`, the Täby fixture with `hojd` and `kommunikation` from the
2027.05 test data, next to the current fixture; it must build, pass the type and label checks,
and report exactly `{"vaglinje": ["ref"]}` as missing.

## Consequences
- An old and a new delivery build with the same code; nothing to choose on the command line.
- A structure change that is *not* additive (a renamed layer or column, a changed object type
  meaning) still fails loudly: unknown layers and unmapped object types are errors.
- **Road numbers.** If real 2027 data has no `vardvagnummer`, road-number shields disappear.
  Lantmäteriet should be asked first (geodatasupport@lm.se); the fallback is NVDB's road-number
  layer (`TNE_FT_Vagnummer_1` / `NVDB_DK_O_*_Vagnummer`), matched like the street names
  (ADR-0007). Real data is expected before May; check it in a v0.3.x.
