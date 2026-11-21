# Changelog

## v0.2.0 – 2026-11-21

"Everyday map": a calmer, searchable map tuned on the Montana 700 in town and in the
mountains, optional street names, and a snowmobile overlay that is readable outdoors. Code,
styles and build instructions only; maps are built locally from the free deliveries.

### Added

- **Street names** from Trafikverket NVDB (CC0) with `build --nvdb-dir` (#60,
  [ADR-0007](docs/adr/0007-street-names-from-nvdb.md)). Topografi 50 roads are matched to
  NVDB name lines (15 m, ±30°, local direction) and split where the name changes: 96 % of
  town-street length named in Täby. Names are drawn from about 80 m, like Karta 1:10 000;
  road numbers stay on every level. The copyright reads "© Lantmäteriet, Trafikverket
  (NVDB)" when used. `scripts/street_name_check.py` checks the matching locally.
- **Search for lakes and terrain names** (#16): Hydrografi and Terrängnamn texts are also
  invisible geographic POIs (`0x6500`, `0x6600`), found under *Where To? → Geographic
  Points*. Towns and villages stay under *Cities*, now listed as "<name>, SE".
- **Road-number shields** (#62): upright boxes (`${ref|highway-symbol:hbox}`).
- `scripts/make_overlay_testgrid.py`: a synthetic snowmobile-trail grid at any point, for
  outdoor checks (#57).

### Changed

- **Fewer labels** (#16), accepted on the device after four rounds:
  - a name split over two lines in Karta 1:50 000 is drawn once (about 23 000 duplicate
    labels nationwide);
  - names enter by Lantmäteriet's text size class: class ≥ 4 from 2 km, 3 from
    650–900 m, 2 from 400 m; church, reserve and information texts from 400 m;
  - place names inside built-up areas come one zoom step later (new tag
    `lm:i_bebyggelse`); in Täby about a sixth of the v0.1 labels at 1.2 km;
  - village and farm names without the device's default dot;
  - protected-area names abbreviated (*naturreservat* → *nr*, *naturvårdsområde* →
    *naturvårdsomr.*), because the Montana cuts labels after about 24 characters.
- **Look** (#14): local streets 2 px and later (1.2 km / 650–900 m), so towns no longer read
  as a grey mass; half-density hatching for reserves and national parks; thin 100 m
  contours at 2 km. Lines are merged regardless of direction (`--allow-reverse-merge`):
  7–10 % fewer lines per level.
- **Snowmobile overlay outdoors** (#57): *Nej* and *Ingen information* are 5 px two-tone
  dashes (light dash, dark gap – Garmin line bitmaps have two colours); the 1836 marker
  has a white ring. Accepted in daylight.
- Tag schema 5 (`lm:gatunamn_nvdb`, `lm:i_bebyggelse`). Style options `relabel`, point
  pattern `label`, line patterns `hatch-sparse` and `dash-long`; `colour2` fills the gaps
  of bitmap lines and rings point icons.

### Measured

| | Result |
|---|---|
| All of Sweden with Topografi 250, cold conversion | 22 min 47 s, peak 4.6 GB RSS |
| Base map / overlay | 1.87 GB (v0.1: 1.89 GB), 410 tiles / 0.9 MB |

See [docs/benchmarks](docs/benchmarks/README.md#2026-11-21--v020-sweden-release-build).

### Device (Montana 700, firmware 25.70)

Every change was tried with a `--dev` map before merging; the record is in
[device-testing.md](docs/device-testing.md). The Montana has no address or street search, so
street names are for display only.

### Known limitations

- NVDB street names need a Lastkajen download per county or for Sweden; the release build
  measured here has none.
- 256 protected-area names are still longer than the device's label limit.
- No routing. Legend-sourced colours, mm-based widths and night colours: #68. The
  Topografi 50 structure change on 2027-05-04 (#56) is parked until test data exist.

## v0.1.0 – 2026-11-20

First release: a nationwide Garmin map from Lantmäteriet's Topografi 50, with a separate
snowmobile overlay, built, verified and accepted on a Garmin Montana 700. The release
contains code, styles and build instructions only. Maps are built locally from the free
Geotorget deliveries; no map data is distributed.

### Maps

- **LM Topo50** (`lm-topo50.img`, family 5750): all 13 themes and 44 layers of Topografi 50.
  Every object type has a style rule or a documented drop. Unicode labels, Sámi characters
  included. Searchable place names. Overview levels use Lantmäteriet's own generalised
  polygons from **Topografi 250** (resolution 18) and optionally **Topografi 100**
  (resolution 20), with joined forest and dissolved lakes when only Topografi 50 is used.
- **LM Skoterleder** (`lm-skoter.img`, family 5751): transparent, toggleable overlay of
  winter trails 1847/1848 styled by *skoterkörning tillåten* (Påbjuden, Ja, Nej, Ingen
  information) and the 1836 mandatory-route markers.
- **OSM Skoterkomplement** (optional, family 5754): snowmobile trails from a local
  OpenStreetMap extract, kept as a separate map (ODbL, for local use).

### Tool (`lm-garmin`)

- `unpack`: zips → local GeoPackage cache with a manifest.
- `convert`: GeoPackage → OSM PBF with style-independent `lm:*` tags
  ([tag schema](docs/tag-schema.md)).
- `build`: convert → splitter → mkgmap per product. Regions: all of Sweden, bounding boxes,
  counties and municipalities by name or SCB code, named development areas, several areas
  in one map. `--dev` builds with their own Garmin IDs. Stage cache: a style edit reuses
  converted data and tiles.
- `style generate`: mkgmap rules, TYP and the [translation table](docs/translation-table.md)
  from `styles/*/mapping.csv`.
- `verify`: decodes the built `.img` (mkgmap's reader) and checks tiles, types and labels;
  CI also enforces per-level feature budgets and snowmobile completeness.
- `coverage`: share of GPX tracks within 25/50 m of the built snowmobile overlay.
- `render`: renders the compiled map and compares it with the Karta 1:50 000 raster.
- `cache`: inspect or clean cached build stages.
- `install`: verified, atomic copy to a connected Garmin, removing macOS `._` files.

### Measured (Apple M5, 16 GB)

| | Result |
|---|---|
| All of Sweden, cold cache | 21 min 36 s, peak 4.6 GB RSS |
| All of Sweden with Topografi 250, cached conversion | 11 min 9 s |
| Base map / overlay | 1.89 GB, 410 tiles / 0.9 MB |
| One county (Gotland) | 19 s |
| Development map (Täby + Hemavan) | about 10 s |

See [docs/benchmarks](docs/benchmarks/README.md).

### Device (Montana 700, firmware 25.70)

Accepted: install, map listing, redraw in seconds, street hierarchy and names in Täby,
contours and Sámi names around Tärnaby, town search (Vallentuna), overlay toggle and all
four trail statuses plus the 1836 marker at Syter. Not yet done: a daylight check of the
overlay at normal brightness. See the [device record](docs/device-testing.md).

### Known limitations

- No street names: Topografi 50 has none (`gatunamn` is empty).
- No routing.
- Label density and priority at the 2 km zoom, and the look of hatching and dashes, still
  need work (#14, #16).
