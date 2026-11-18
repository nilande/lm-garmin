# 0005 – Label encoding: Unicode if the device accepts it

Status: Proposed – **needs device test** · 2026-11-18

## Context
1 017 place names (mostly Sami, in the mountains) contain č, Č, ŋ, đ, ŧ – not in cp1252.
mkgmap supports `--code-page=1252` (Latin-1 style) and `--unicode`. Reports conflict on
whether newer Garmin models accept unsigned Unicode maps (GPSMAP 66 reported OK; some other
models refuse). No report found for the Montana 700.

## Options
1. `--unicode` (+ UTF-8 TYP). Correct names everywhere.
2. `--code-page=1252` with transliteration of the five characters. Works on every device;
   names slightly wrong (e.g. "Ciekngaljávri").

## Decision (provisional)
Make encoding a build option. Default to **Unicode** if the Montana 700 test passes,
otherwise cp1252 with documented transliteration.

## Evidence
Spike S3: Unicode build works in mkgmap, labels decode correctly; the TYP source must then be
UTF-8 with `CodePage=65001` (a cp1252-encoded file fails without a useful message).
Device kit in `spikes/06-device-test/` contains both variants.
