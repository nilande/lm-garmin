# Changelog

## Unreleased

### Added

- Street names from Trafikverket NVDB (CC0) with `build --nvdb-dir` (#60,
  [ADR-0007](docs/adr/0007-street-names-from-nvdb.md)). Topografi 50 roads are matched to
  NVDB name lines and split where the name changes. In Täby 96 % of town-street length is
  named. New tag `lm:gatunamn_nvdb`, tag schema 4. The copyright reads "© Lantmäteriet,
  Trafikverket (NVDB)" when used.
- `scripts/street_name_check.py`: local quality check of the matching.

### Changed

- Labels (#16): a name split over two lines in Karta 1:50 000 is drawn once (Topografi 50
  stores the full name on every part: about 23 000 duplicate labels nationwide). Church
  and protected-area names from resolution 22, so they no longer repeat town and reserve
  names at the overview levels. Names are thinned by Lantmäteriet's text size class: class ≥ 4 from
  2 km, class 3 from 650–900 m, class 2 from 400 m (about a quarter of the labels at 1.2 km
  in Täby compared with v0.1). Place names inside built-up areas (new tag
  `lm:i_bebyggelse`, tag schema 5) come one zoom step later than in the countryside. Search
  results read "<name>, SE" instead of mkgmap's default "ABC". Village and farm names
  (`0x0a00`/`0x0c00`) are drawn without the device's default dot.
- Look (#14): local streets are 2 px and start at 1.2 km (Lokalgata stor) and 650–900 m
  (Lokalgata liten), so towns no longer read as a grey mass at 1.2–2 km. Nature reserves
  and national parks use a hatch of half the density (new pattern `hatch-sparse`).
- Search (#16): lake, stream and terrain names are also written as invisible geographic
  POIs (`0x6500` water, `0x6600` land) at the most detailed level, so they can be found
  under *Where To? → Geographic Points*. The visible name stays a label point.
- Labels (#16): the Montana cuts labels after about 24 characters; protected-area names
  abbreviate *naturreservat* → *nr* and *naturvårdsområde* → *naturvårdsomr.* (new style
  option `relabel`).
- Look (#14): the 100 m index contours at 2 km use the thin minor-contour type, so steep
  mountains no longer turn dark at that zoom.
- Road numbers are drawn as upright box shields (`${ref|highway-symbol:hbox}`), and lines
  are merged regardless of direction (`--allow-reverse-merge`): 7–10 % fewer lines per
  level and fewer, steadier road-number labels (#62).
- Style: road numbers at every level; street names only at resolution 23–24 (about 80 m
  and closer), like Karta 1:10 000, after the Montana check.

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
