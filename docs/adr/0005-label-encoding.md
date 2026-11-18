# 0005 – Label encoding: Unicode if the device accepts it

Status: Accepted · 2026-11-18 (device test, issue #1)

## Context
1 017 place names (mostly Sami, in the mountains) contain č, Č, ŋ, đ, ŧ – not in cp1252.
mkgmap supports `--code-page=1252` (Latin-1 style) and `--unicode`. Reports conflict on
whether newer Garmin models accept unsigned Unicode maps (GPSMAP 66 reported OK; some other
models refuse). No report found for the Montana 700.

## Options
1. `--unicode` (+ UTF-8 TYP). Correct names everywhere.
2. `--code-page=1252` with transliteration of the five characters. Works on every device;
   names slightly wrong (e.g. "Ciekngaljávri").

## Decision
Build with **`--unicode`** (and a UTF-8 TYP) by default. No transliteration. cp1252 remains
a build option for older devices; mkgmap then writes ŋ as "NG" (seen in spike S6).

## Device result (Montana 700, 2026-11-18)
- Unicode maps from mkgmap load without signing (base map and overlay).
- A diagnostic map with one label per character showed **á, ŋ, č, Č, đ and ŧ correctly** on
  city points (`0x0c00`) and label points (`0x2800`).
- Labels did *not* show on water/land-feature POIs (`0x650d`, `0x6614`) – a type issue, not an
  encoding issue (see docs/spikes.md § S6 and issue #16).

## Evidence
Spike S3: Unicode build works in mkgmap, labels decode correctly; the TYP source must then be
UTF-8 with `CodePage=65001` (a cp1252-encoded file fails without a useful message).
Device kit in `spikes/06-device-test/` contains both variants.
