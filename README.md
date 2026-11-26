# lm-garmin

Build a Garmin map (`.img`) from Lantmäteriet's open topographic data
**Topografi 50 Nedladdning, vektor**, styled to resemble Lantmäteriet's printed
**Karta 1:50 000**. Primary target device: **Garmin Montana 700**.

> **v0.4.0** – the nationwide base map with NVDB street names, street search, terrain shading
> and night colours, and the separate Lantmäteriet snowmobile overlay, are built, verified and
> accepted on a Garmin Montana 700; the converter is ready for Lantmäteriet's 2027 structure
> change. See [CHANGELOG.md](CHANGELOG.md), the
> [device test record](docs/device-testing.md) and [AGENTS.md](AGENTS.md) for the state of the
> project and next steps.

Map data © Lantmäteriet (CC0). This repository contains **no map data** except small test
cut-outs in [`tests/data`](tests/data/PROVENANCE.md).

## What it does

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
4. Recommended for the overview zoom levels: order **Topografi 250 Nedladdning, vektor**,
   area *Sverige*, GeoPackage (also free, CC0). Only its `mark_sverige.zip` is used. Unpack
   it into a folder of its own:

   ```bash
   mkdir -p "/path/to/topografi250/gpkg"
   unzip -j "/path/to/LM…:… - Topografi 250 Nedladdning, vektor/mark_sverige.zip" '*.gpkg' \
     -d "/path/to/topografi250/gpkg"
   ```

   Without it the map still builds, but large areas at the 8 km zoom show the dark
   background colour ([device test](docs/device-testing.md#täby-overview-retest)).
5. Optional, for **street names**: Trafikverket's road database **NVDB** (CC0). Create a
   free account at [Lastkajen](https://www.trafikverket.se/lastkajen) and open *Färdiga
   datapaket → 1. Väg → Länsfiler NVDB-data*. Download the **GeoPackage** file of each
   county you build (`<Län>_geopackage.zip`; all 21 for Sweden). The FileGDB file of a county
   has the same content and also works; for **Dalarnas län** take the FileGDB file, since its
   GeoPackage zip on Lastkajen holds no data (2026-11). The nationwide *Sverigefiler utvalda
   NVDB-data* have **no** street names. A county file is 0.2–2.2 GB unpacked with about 124 layers; keep only the
   two name layers (`NVDB_DK_O_20_Gatunamn`, `NVDB_DK_O_21_Ovrigt_vagnamn`) in one small
   GeoPackage, without unpacking the zips yourself:

   ```bash
   uv run lm-garmin nvdb extract "/path/to/lastkajen-zips" --out "/path/to/nvdb/nvdb-names.gpkg"
   ```

   All 21 counties give 898 000 name lines in a 356 MB file (2 min 40 s). A sidecar
   `nvdb-names.json` records the source files, checksums and each delivery's
   *Betraktelsedatum* (from `Leveransinformation_*.txt`; FileGDB zips have none), and the
   build report repeats the dates under `nvdb`.

6. Optional: **Topografi 100** (same steps) for the 2 km overview level, and
   **Karta 1:50 000 Nedladdning, raster** (GeoTIFF) for visual comparison.
7. Optional, for **terrain shading**: order **Markhöjdmodell Nedladdning, grid 50+** for
   the counties you build (or all of Sweden: 76 zips, 1.6 GB). Keep the zips (`71_5.zip`, …)
   as delivered in one folder; the `metadata/` folder is not used.

Keep the delivery anywhere; paths may contain spaces and colons
(e.g. `LM2026:173692 - Topografi 50 Nedladdning, vektor`).

## Build a map

```bash
# S0: unpack the delivery once into the cache (~/.cache/lm-garmin/gpkg); re-runs are no-ops
uv run lm-garmin unpack "/path/to/LM2026:173692 - Topografi 50 Nedladdning, vektor"

# S1–S3: build the maps for a region. The release map (≈ 23 min, about 2.3 GB):
uv run lm-garmin build --region sweden --topo250-dir "/path/to/topografi250/gpkg" \
  --nvdb-dir "/path/to/nvdb" --dem-dir "/path/to/grid50+" --out dist/
# smaller regions
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

Add `--nvdb-dir "/path/to/nvdb"` (the folder with `nvdb-names.gpkg`, or with unpacked county
GeoPackages) to name streets and small roads from NVDB. Topografi 50
roads are matched to NVDB name lines by distance (15 m), direction (±30°) and overlap, and
split where the name changes ([how](docs/street-names.md)). Street names are drawn only at
the most detailed zoom (about 80 m and closer); roads with a road number keep the number on
every level. The base map's copyright then reads "© Lantmäteriet, Trafikverket (NVDB)" (the
device adds the "©").
Matching adds about 20 s per county; the result is cached per region and NVDB file.

```bash
uv run lm-garmin build --area taby --dev --nvdb-dir "/path/to/nvdb" --out dist/dev
```

Add `--dem-dir "/path/to/grid50+"` to put a terrain model in the base map for **hill
shading** (#90). The 50 m grid is turned into 1° elevation tiles (cached per region and
delivery) and added with mkgmap's `--dem`. The map grows by about a third. On the Montana
700, turn on *Map › Map Sets › Shaded Relief*; shading shows in day colours and down to the
120 m scale ([device test](docs/device-testing.md#2026-11-24--terrain-shading-90)).

```bash
uv run lm-garmin build --municipality Storuman --dev --dem-dir "/path/to/grid50+" --out dist/dev
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
the GeoPackage spatial index for the bounding box, keeps objects that intersect
the boundary polygon and cuts those that cross it at the boundary, so the map
ends cleanly at the county or municipality border. Bounding-box regions and
Sweden are not clipped.

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
Street names (optional): Trafikverket NVDB, CC0; maps built with them also carry
"Trafikverket (NVDB)". Terrain model (optional): Lantmäteriet Markhöjdmodell grid 50+, CC0.
mkgmap and splitter (GPL-2.0) are downloaded at build time and run as separate programs.

### Sharing built maps

Maps built with the default products (`lm-topo50.img`, `lm-skoter.img`) contain only CC0
data, so you may copy, give away or sell them. This is our reading of the licences, not
legal advice.

- **Data.** Topografi 50 and 250, Markhöjdmodell grid 50+ (Lantmäteriet) and NVDB
  (Trafikverket) are CC0: no permission, attribution or share-alike needed. Keep the source
  notice that the maps carry ("Lantmäteriet, Trafikverket (NVDB)") and state the delivery
  dates (in `build-report.json`) so users know how current the map is.
- **Tools.** The GPL of mkgmap and splitter covers the programs, not the maps they write.
  The MIT licence of this project needs no notice in the map files; include `LICENSE` if you
  pass on the code.
- **OpenStreetMap.** The optional `skoter-osm` overlay and any Skoterleder.org data are
  OpenStreetMap data under the [ODbL](https://www.openstreetmap.org/copyright). A map built
  from it must say "© OpenStreetMap contributors", and the ODbL's share-alike rules apply to
  the underlying data. Leave it out, or follow the ODbL, when you share maps.
- **No endorsement.** Do not suggest that Lantmäteriet, Trafikverket or Garmin made or
  approve the map, and do not use their logos. Naming them as data sources, or saying the
  map works on a Garmin Montana 700, is fine.
- **Garmin.** Garmin's licence for the device software forbids reverse-engineering the
  device software; it does not cover maps you load on the device, and copying a `.img` to
  `Garmin/` changes no device software. Garmin's own map products have their own licences
  and are not part of these maps.
- **No warranty.** The data comes as is. If you sell maps, you answer to your buyers under
  consumer law; say that the map is not meant for safety-critical navigation.

---

## Sammanfattning på svenska

`lm-garmin` gör om Lantmäteriets öppna **Topografi 50** till en Garmin-karta (`.img`) för
i första hand **Garmin Montana 700**, med ett utseende som liknar **Karta 1:50 000**.
Skoterlederna i Lantmäteriets data (vinterleder med uppgift om skoterkörning är tillåten,
påbjuden eller förbjuden) byggs som ett eget genomskinligt lager som kan slås av och på
i enheten. Ortnamn, sjöar och fjäll blir sökbara.

Data hämtas gratis från Geotorget (se ovan): Topografi 50 och, för översiktsnivåerna,
Topografi 250. Gatunamn kan läggas till från Trafikverkets NVDB (Lastkajen, CC0) med
`--nvdb-dir`, efter `lm-garmin nvdb extract` på länsfilerna. Hela Sverige med gatunamn
byggs på cirka 23 minuter till en karta på 2,3 GB. Med `--dem-dir` och Markhöjdmodell grid 50+
får kartan terrängskuggning, och gator går att söka fram under *Vart? › Adresser*. Kartan har
också nattfärger. Version 0.4.0 är provad och godkänd på en Montana 700. Gatunamn, höjdkurvornas siffror och
POI-symboler kan slås av och på per aktivitetsprofil i enheten. Repot innehåller ingen kartdata utöver små
testutsnitt. Planen finns i [docs/PLAN.md](docs/PLAN.md), läget och nästa steg i
[AGENTS.md](AGENTS.md), och arbetet följs i GitHub Issues. Koden är MIT-licensierad;
data © Lantmäteriet (CC0). Byggda kartor med enbart Lantmäteriets och Trafikverkets data
(CC0) får kopieras, ges bort och säljas, så länge man inte antyder att Lantmäteriet,
Trafikverket eller Garmin står bakom dem. Kartor med OpenStreetMap-data följer ODbL. Se
[Sharing built maps](#sharing-built-maps).
