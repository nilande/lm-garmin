# lm-garmin

Build a Garmin map (`.img`) from Lantmäteriet's open topographic data
**Topografi 50 Nedladdning, vektor**, styled to resemble Lantmäteriet's printed
**Karta 1:50 000**. Primary target device: **Garmin Montana 700**.

> Work toward [v0.1 MVP](https://github.com/nilande/lm-garmin/milestone/7) focuses on
> verifying the nationwide base map and the separate Lantmäteriet snowmobile overlay
> on the Montana 700. See the [release plan](docs/PLAN.md#v01-mvp).

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

### Rebuild after editing a style

Run the same `build` command after editing the style. Data conversion, geographic
extracts and Garmin tile splitting are reused for matching inputs. Only products
with a changed generated style are recompiled. The first build fingerprints its
input files. Later builds reuse digests while the file metadata matches, and
`build-report.json` marks reused stages with `cached: true`.

`lm-garmin cache info` reports the number and size of cached stage outputs.
`lm-garmin cache clean` removes the stage cache. The unpacked source GeoPackages,
downloaded tools and maps already written to the output directory are preserved.

### Build by county or municipality

Download the ArcView-shape ZIP from [SCB's digital boundaries](https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/digitala-granser/)
and pass the ZIP as downloaded. The default is `admin-index.zip` in the build
cache. Both `build` and `convert` accept names or SCB codes.

```bash
uv run lm-garmin build --county "Jämtlands län" --admin-index /path/to/scb.zip
uv run lm-garmin build --municipality Storuman --admin-index /path/to/scb.zip --dev
```

The build matches names to closed polygons made from Topografi 50 boundary lines
and reports when it uses a simplified SCB polygon instead. The converter uses
the GeoPackage spatial index for the bounding box and then keeps objects that
intersect the boundary polygon. Topografi 50 objects crossing it are retained as
whole features. The Garmin tile itself is rectangular.

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

### Compare the base map to Karta 1:50 000

Compare a built map with a reference GeoTIFF covering the same area.

```bash
uv run lm-garmin render dist/dev/lm-dev-topo50.img \
  --reference tests/data/tatort_659_67_00.ref50k.tif --out dist/raster-taby
```

The comparison uses a common SWEREF 99 TM grid at 5 metres per pixel. Use `--bbox`
for a smaller window, `--level` to inspect a Garmin overview, and `--style-mapping`
if the map was built from a different `mapping.csv`. With a reference, the command
writes a side-by-side PNG (reference left), a difference PNG and per-class IoU in
`comparison.json`. A bbox alone produces `render.png`.

The preview uses the matching TYP colours, fill patterns and polygon draw order.
It approximates line strokes and leaves text and Garmin's own placement rules to
the device. Read [how to interpret the comparison](docs/raster-comparison.md).

### Measure snowmobile trail coverage

```bash
uv run lm-garmin coverage --img dist/lm-skoter.img --gpx "/path/to/tracks"
```

Pass a GPX file or a directory of GPX files. The command samples track segments at
intervals of up to 5 m and reports the share of track length within 25 m and 50 m
of any trail in the decoded snowmobile overlay, across all four status values.
Use an overlay that covers the same region as the reference tracks. The command
prints aggregate figures. GitHub Actions checks the synthetic track in `tests/data/tracks/`.

The optional Skoterleder.org regression check uses local GPX files for comparison.
The [optional supplement](#add-the-optional-openstreetmap-snowmobile-supplement)
reads OpenStreetMap directly. For the comparison, build the same region as the
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
3. Eject, restart the device, then use *Map Manager* to enable or disable the base
   map and the snowmobile overlay. Disable other maps covering the same area if
   they hide this one. See the [Montana release checklist](docs/device-testing.md#release-checklist).

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
