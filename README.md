# lm-garmin

Build a Garmin map (`.img`) from Lantmäteriet's open topographic data
**Topografi 50 Nedladdning, vektor**, styled to resemble Lantmäteriet's printed
**Karta 1:50 000**. Primary target device: **Garmin Montana 700**.

> **Status: milestone M1 (MVP) in progress.** `unpack`, `convert`, `build` and `verify`
> work; the style is a first draft; see [docs/PLAN.md](docs/PLAN.md) and the
> [milestones](https://github.com/nilande/lm-garmin/milestones). Experiments that informed
> the plan are in [`spikes/`](spikes) and [docs/spikes.md](docs/spikes.md).

Map data © Lantmäteriet (CC0). This repository contains **no map data** except small test
cut-outs in [`tests/data`](tests/data/PROVENANCE.md).

## What it will do

- Convert all 13 themes of Topografi 50 (GeoPackage, SWEREF 99 TM) to a routable-ready
  OSM intermediate, then compile it with [mkgmap](https://www.mkgmap.org.uk/) and a custom
  style and TYP file into `gmapsupp.img`.
- Build all of Sweden or just a region (bounding box, county, municipality).
- Build Lantmäteriet's snowmobile information (winter trails with *skoterkörning tillåten*
  Ja / Påbjuden / Nej / Ingen information, mandatory snowmobile routes) as a **separate,
  transparent overlay** that can be switched on and off on the device.
- Make place names searchable on the device.
- Verify the built map by decoding it again (snowmobile completeness, coverage metrics,
  rendering for visual comparison with Karta 1:50 000).

## Requirements

- Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/)
- Java ≥ 17 (for mkgmap and splitter)
- GDAL command line tools – only for `scripts/make_fixtures.py`
- ~20 GB free local disk for the unpacked data cache (all of Sweden)

On macOS:

```bash
brew install uv openjdk gdal
```

## Install (development)

```bash
git clone https://github.com/nilande/lm-garmin.git
cd lm-garmin
uv sync
uv run lm-garmin tools fetch      # downloads pinned mkgmap and splitter, verifies SHA-256
uv run pytest
```

## Get the data from Geotorget

1. Create a free account at [Geotorget](https://geotorget.lantmateriet.se/).
2. Order **Topografi 50 Nedladdning, vektor** (*Geodataprodukter → Topografi 50
   Nedladdning, vektor → Beställning*), area *Sverige* (or a county), format GeoPackage.
   The product is free (CC0).
3. Download the delivery. You get one zip per theme (`hojd_sverige.zip`, `mark_sverige.zip`, …)
   and `uttag.json` — about 5.4 GB zipped, 15.3 GB unpacked for all of Sweden.
4. Optional, for visual comparison: order **Karta 1:50 000 Nedladdning, raster** (GeoTIFF)
   for the same area.

Keep the delivery anywhere; paths may contain spaces and colons
(e.g. `LM2026:173692 - Topografi 50 Nedladdning, vektor`).

## Build a map

```bash
# S0: unpack the delivery once into the cache (~/.cache/lm-garmin/gpkg); re-runs are no-ops
uv run lm-garmin unpack "/path/to/LM2026:173692 - Topografi 50 Nedladdning, vektor"

# S1–S3: build the maps for a region
uv run lm-garmin build --region sweden --out dist/
uv run lm-garmin build --bbox 500000,7250000,550000,7310000 --out dist/   # SWEREF 99 TM
uv run lm-garmin build --bbox-wgs84 14.5,65.4,16.0,65.9 --out dist/

# S4: decode the built maps and check them
uv run lm-garmin verify dist/lm-topo50.img dist/lm-skoter.img
```

For the base map, pass either or both directories of unpacked nationwide
GeoPackages in SWEREF 99 TM to use Lantmäteriet's generalized polygons at the
overview levels. Each directory must contain its delivery's `mark_sverige.gpkg`.

```bash
uv run lm-garmin build --area hemavan --dev --products topo50 \
  --topo100-dir "/path/to/topografi100/gpkg" --topo250-dir "/path/to/topografi250/gpkg"
```

Topografi 100 replaces land cover, water surfaces and wetlands at resolution 20.
Topografi 250 replaces them at resolution 18. Each option works independently.
If omitted, the corresponding level uses Topografi 50. Names, roads and trails
continue to come from Topografi 50. See the [overview source plan](docs/overview-sources.md).

Output in `dist/`:

| File | Contents |
|---|---|
| `lm-topo50.img` | base map (family id 5750), searchable place names |
| `lm-skoter.img` | transparent snowmobile overlay (family id 5751), only if the region has winter trails |
| `osm-skoter.img` | optional, independently toggleable OpenStreetMap supplement (family id 5754) |
| `build-report.json` | time and peak memory per step, tile counts, sizes |

### Add the optional OpenStreetMap snowmobile supplement

```bash
uv run lm-garmin build --area hemavan --osm /path/to/region.osm.pbf --dev --out dist/dev
# Or use --products skoter-osm to build just the supplement.
```

Use an OpenStreetMap `.osm` or `.osm.pbf` extract with complete way nodes. Providing
`--osm` adds a separate **OSM Skoterkomplement** map alongside the default Lantmäteriet
products. The development filename is `osm-dev-skoter.img`. Install it like the
other maps and toggle it in Map Manager.

Teal identifies the OpenStreetMap source. A solid line marks `snowmobile=designated`,
a dashed line marks `yes` or `permissive`, and a dotted line marks `ice_road=yes`
with one of those access tags. These are OSM tags, including the ice-road tag.
The supplement keeps stretches that differ from Topografi 50. It uses a 40 m
corridor around the source winter trails and treats overlaps of at least 120 m,
or 80% of a shorter way, as matches. It retains short crossings and drops
fragments under 30 m left by an overlap. All Lantmäteriet trail statuses count
when finding matches, including `Nej`.

The overlay carries **© OpenStreetMap contributors** attribution. The source is
available under the [OpenStreetMap ODbL terms](https://www.openstreetmap.org/copyright).

### Development loop (iterating on the look)

```bash
# ~10 s: Täby (town) + Hemavan–Syter (mountains, snowmobile trails) in one small map
uv run lm-garmin build --area taby --area hemavan --dev --out dist/dev
# copy to a connected device: verified, atomic, removes macOS ._ files
uv run lm-garmin install dist/dev/lm-dev-topo50.img dist/dev/lm-dev-skoter.img
```

`--dev` maps use their own family ids (5752/5753) and file names (`lm-dev-*.img`), so they can
sit next to the full map on the device; switch one of them off in *Map Manager* while
comparing. `--bbox` can also be repeated to combine several areas.

Use `lm-garmin convert …` to run S1 by itself. Use `lm-garmin style generate`
to regenerate the mkgmap styles, TYP files and the
[translation table](docs/translation-table.md) from `styles/*/mapping.csv`.

### Measure snowmobile trail coverage

```bash
uv run lm-garmin coverage --img dist/lm-skoter.img --gpx "/path/to/tracks"
```

Pass a GPX file or a directory of GPX files. The command samples track segments at
intervals of up to 5 m and reports the share of track length within 25 m and 50 m
of any trail in the decoded snowmobile overlay, across all four status values.
Use an overlay that covers the same region as the reference tracks. The command
prints aggregate figures. GitHub Actions checks the synthetic track in `tests/data/tracks/`.

The Skoterleder.org regression check is local. Build the same region as the
[coverage spike](docs/spikes.md#s5--coverage-against-skoterlederorg-gpx-spikes05-coverage):

```bash
uv run lm-garmin build --bbox 470000,7240000,595000,7320000 --products skoter --out dist/coverage
uv run pytest -q -m local_data --capture=tee-sys
```

The check defaults to `dist/coverage/lm-skoter.img` and
`/Volumes/scratch/lm-kartdata/snowmobile tracks`. Override these with
`LM_GARMIN_COVERAGE_IMG` and `LM_GARMIN_COVERAGE_GPX`. The test skips when the GPX
files are missing and fails if coverage within 50 m falls below 44.9%, one
percentage point below the 45.9% baseline. Keep the reference tracks local.

## Install on the Montana 700

1. Connect the device with USB (it appears as a drive), or put its microSD card in a reader.
2. Copy `lm-topo50.img` and `lm-skoter.img` to the `Garmin/` folder (internal storage or
   SD card). Files must be < 4 GB (FAT32); the build fails above 3.5 GB.
3. Eject, restart the device, then *Map setup → Map information* (*Kartinställningar →
   Kartinformation*) to enable/disable the base map and the snowmobile overlay. Disable other
   maps covering the same area if they hide this one.

## Licence and attribution

Code, styles and TYP sources: [MIT](LICENSE). Map data: Lantmäteriet, CC0 – attribution is
not required, but maps built with this tool carry "© Lantmäteriet" and we ask you to keep it.
mkgmap and splitter (GPL-2.0) are downloaded at build time and run as separate programs.

---

## Sammanfattning på svenska

`lm-garmin` gör om Lantmäteriets öppna **Topografi 50** till en Garmin-karta (`.img`) för
i första hand **Garmin Montana 700**, med ett utseende som liknar **Karta 1:50 000**.
Skoterlederna i Lantmäteriets data (vinterleder med uppgift om skoterkörning är tillåten,
påbjuden eller förbjuden) byggs som ett eget genomskinligt lager som kan slås av och på
i enheten. Ortnamn blir sökbara.

Data hämtas gratis från Geotorget (se ovan). Repot innehåller ingen kartdata utöver små
testutsnitt. Projektet är i början: planen finns i [docs/PLAN.md](docs/PLAN.md) och arbetet
följs i GitHub Issues. Koden är MIT-licensierad; data © Lantmäteriet (CC0).
