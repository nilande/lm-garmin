# AGENTS.md – working on lm-garmin

Guide for coding agents (Codex, Claude Code) and new contributors. Read this first, then
[docs/PLAN.md](docs/PLAN.md).

## What this is

A Python CLI that turns Lantmäteriet's **Topografi 50** (GeoPackage, CC0) into Garmin `.img`
maps for a **Garmin Montana 700**: a base map (`lm-topo50.img`) styled like Karta 1:50 000,
plus a transparent **snowmobile overlay** (`lm-skoter.img`).

Pipeline: `unpack` (zip → GeoPackage cache) → `convert` (GeoPackage → OSM PBF with `lm:*`
tags) → splitter → mkgmap (style + TYP generated from `styles/*/mapping.csv`) → `verify`
(decode the built `.img` with `java/ImgDump.java`).

## Commands

```bash
uv sync && uv run lm-garmin tools fetch          # deps + pinned mkgmap r4924 / splitter r654
uv run ruff check . && uv run ruff format --check .
uv run pytest -q                                  # unit tests (~2 s)
uv run pytest -q -m integration                   # builds the 3 fixtures to .img (~15 s, needs Java)
uv run lm-garmin style generate                   # after editing styles/*/mapping.csv – commit the output
uv run lm-garmin build --area taby --area hemavan --dev --out dist/dev   # ~10 s dev map
uv run lm-garmin build --region sweden --out dist/sweden                 # ~17 min, 2 GB
uv run lm-garmin verify dist/dev/lm-dev-topo50.img
uv run lm-garmin install dist/dev/*.img           # to a connected device at /Volumes/GARMIN
```

Java: `$LM_GARMIN_JAVA`, `$JAVA_HOME`, Homebrew `openjdk` or `java` on PATH (17+).
Data cache: `$LM_GARMIN_CACHE` or `~/.cache/lm-garmin` (unpacked GeoPackages in `gpkg/`).

## Rules

- **No map data in the repo**, releases or CI artifacts. The only exception is `tests/data/`
  (three clipped fixtures + two raster cut-outs, made by `scripts/make_fixtures.py`).
- **Never commit the Skoterleder.org GPX** (OSM-derived, ODbL); use it only locally.
- Code, docs and issues in **English**; the README has a Swedish summary.
- Styles: edit only `mapping.csv`, then run `lm-garmin style generate`; the generated files
  carry a header and a test fails if they are stale. Every Lantmäteriet object type needs a
  row (or a `drop` row with a reason) – a test enforces it.
- Garmin ids: base 5750, overlay 5751, dev builds 5752/5753 (`products.py`). Every map file
  must have its own tile-number range, or the device silently skips it.
- Keep `THEME_LAYERS` order in `convert.py` fixed (it defines OSM id ranges); bump
  `SCHEMA_VERSION` in `tags.py` when tag meaning changes (`docs/tag-schema.md`).
- Commit messages end with a `Co-Authored-By:` line for the agent; PRs go to `main`.

## Device lessons (Montana 700) – see docs/device-testing.md

- Unicode maps work (Sami á ŋ č Č đ ŧ display correctly).
- Labels are drawn only for city types (`0x0100`–`0x1100`) and label points (`0x28xx`),
  **not** for `0x65xx`/`0x66xx` POIs → map texts are `0x2800`/city points.
- Roads must use standard road types (`0x01`–`0x13`); extended line types were not visible.
- Contour labels are read as **feet** by the device → label `${ele|conv:m=>ft}`.
- TYP line widths are fixed pixels, independent of zoom.
- Extended types: subtype ≤ `0x1f` (mkgmap rejects more); a fully transparent TYP line is
  rejected (use pattern `label`).

## Release status

The [v0.1 MVP milestone](https://github.com/nilande/lm-garmin/milestone/7)
tracks the default nationwide build (#11), Garmin IDs (#3) and one Montana
device session for the base and overlay (#12, #20, #24). See the
[release plan](docs/PLAN.md#v01-mvp) and
[device checklist](docs/device-testing.md#release-checklist). GitHub issues
track subsequent style, search and performance work.

## Where things are

| Path | What |
|---|---|
| `src/lm_garmin/` | `unpack`, `region`, `tags`, `convert`, `products`, `stylegen`, `build`, `verify`, `install`, `tools`, `cli` |
| `styles/topo50/mapping.csv`, `styles/skoter/mapping.csv` | the style sources |
| `java/ImgDump.java` | `.img` decoder on mkgmap's reader classes |
| `tests/unit`, `tests/integration`, `tests/data` | tests and fixtures (+ `expect/*.json`) |
| `docs/` | PLAN, ADRs, data inventory, tag schema, spikes, device testing, benchmarks |
| `spikes/` | throw-away planning experiments – not production code |
