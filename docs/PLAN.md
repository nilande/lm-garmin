# Plan — Topografi 50 → Garmin `.img`

Status: **accepted** 2026-11-18 (all proposals in §13 approved). The `spikes/` folder holds
throw-away experiments that de-risked the plan (see [spikes.md](spikes.md)); work is tracked
in GitHub Issues per milestone (§12).

## 1. Goal and scope

Build an open-source command-line tool that turns Lantmäteriet's **Topografi 50
Nedladdning, vektor** (GeoPackage, CC0) into a Garmin map (`.img`) for the
**Garmin Montana 700**, looking as much as practical like **Karta 1:50 000**.

| In the first release (MVP) | Later |
|---|---|
| All 13 themes translated to Garmin types | Routing on `vaglinje` (and winter trails) |
| One default style (mkgmap style + TYP as source) that resembles Karta 1:50 000 | Alternative styles (e.g. high-contrast, winter) |
| Build for all of Sweden, or a bbox / county / municipality | Optional supplement built from a local OpenStreetMap extract |
| Separate, transparent snowmobile overlay from LM data | Automatic Geotorget download via API |
| Town names searchable on the Montana 700 | Production lake and mountain search, further labelling and contour tuning |
| CI: lint, unit tests, fixture builds and decode verification | CI performance trends and release packaging (Homebrew tap / pipx) |

Non-goals: raster maps (`.img` is vector only; a raster would be a Garmin *Custom Map*
KMZ, a different product), Garmin-signed maps, distributing built maps or map data.

## 2. Architecture

```
            ┌──────────────────────────── cache (~/.cache/lm-garmin) ─────────────────────────────┐
 zip ──S0──▶ gpkg/<tema>.gpkg ──S1──▶ pbf/<region>/<tema>.osm.pbf ──S2──▶ tiles/<region>/*.pbf ──S3──▶ img/
 (NAS)  unpack once        extract+convert          split (splitter)            mkgmap + style + TYP
                           (R-tree, stream,         stable areas.list           gmapsupp.img (base)
                            WGS84, lm:* tags)                                   + overlay .img (skoter)
                                                                                      │
                                                                                 S4 verify: decode .img
                                                                                 (MapReader) → checks,
                                                                                 coverage, render, report
```

| Stage | Input → output | Tool | Rebuilt when |
|---|---|---|---|
| **S0 unpack** | delivery zips → one GPKG per theme on local SSD | Python `zipfile` (streamed) | zip changes (size + mtime + `uttag.json`) |
| **S1 convert** | GPKG layers in region → OSM PBF per theme, EPSG:4326, `lm:*` tags | Python: pyogrio (Arrow) + shapely + pyproj + pyosmium | data, region or *converter version* changes |
| **S2 split** | theme PBFs → mkgmap tiles | splitter (Java) | S1 output changes; `areas.list` reused for stable tile ids |
| **S3 compile** | tiles + style + TYP → `.img` | mkgmap (Java) | S2 output **or style/TYP** changes |
| **S4 verify** | `.img` → GeoJSON → checks/metrics/renders | mkgmap `MapReader` (Java, tiny helper) + Python | always in CI; on demand locally |

Key design rule (ADR-0003): **S1 is style-independent.** The converter only re-encodes
Lantmäteriet's own attributes as OSM tags (`lm:l`, `lm:t`, `lm:sk`, …). Every visual
decision — Garmin type, zoom level, label — lives in the mkgmap style and the TYP file.
A style change therefore only re-runs S3 (minutes, not the whole pipeline).

The snowmobile overlay is a second, independent build target from the same S1 output
(filtered) with its own style, TYP and family id (ADR-0004).

### 2.1 Repository layout (proposed)

```
lm-garmin/
├── src/lm_garmin/            # Python package (CLI: `lm-garmin`)
│   ├── cli.py                #   build, unpack, extract, fixtures, verify, tools fetch
│   ├── unpack.py  extract.py  osmwrite.py  regions.py  tools.py  verify/ …
├── styles/
│   ├── topo50/               # default mkgmap style (lines, polygons, points, options, info)
│   │   └── typ/topo50.txt    # TYP source, compiled by mkgmap
│   └── skoter/               # overlay style + typ/skoter.txt
├── java/ImgDump.java         # decoder used by verification (runs on mkgmap.jar)
├── tests/
│   ├── data/                 # fixtures: 3 clipped GeoPackages (≤ 3 MB each) + PROVENANCE.md
│   │   └── tracks/           # hand-made test GPX for CI coverage check
│   ├── unit/  integration/
├── scripts/make_fixtures.py  # re-creates tests/data from a Topografi 50 delivery
├── docs/ PLAN.md  data-inventory.md  spikes.md  adr/  translation-table.md  device-testing.md
├── spikes/                   # planning experiments – not production code
└── .github/workflows/ci.yml
```

## 3. Pipeline details

### 3.1 S0 – unpack and cache

- Never read GeoPackage from inside the zip (deflate, no random access).
- Unpack each theme once to `${LM_GARMIN_CACHE:-~/.cache/lm-garmin}/gpkg/`, skipping `._*`
  and `.DS_Store`; write a manifest with source size/mtime and the `uttag.json` hash.
- Measured: NAS → SSD 89 MB/s; whole delivery unpacks in ~100 s. Not a bottleneck.
- Paths are always taken as arguments and passed as `pathlib.Path` – the delivery folder name
  contains `:`, `,` and spaces.

### 3.2 S1 – extract and convert

- Region = bbox in EPSG:3006 (from CLI bbox, county/municipality polygon, or "sweden").
  Features are selected with the GeoPackage **R-tree** (`pyogrio.read_arrow(bbox=…)` /
  spatial filter). **No geometric clipping** – splitter/mkgmap handle tile edges, and
  clipping was the slowest step in the spike (62 s vs 17 s for 50×50 km).
- Read in Arrow batches (pyogrio `use_arrow=True`), transform with pyproj vectorised,
  write **OSM PBF** with pyosmium. Streaming, bounded memory per batch.
- One PBF per theme ⇒ themes are converted **in parallel** (process pool). Each theme gets
  its own OSM id range so files can be fed to splitter together; ids are positive and
  ascending (splitter requirement, found in spike S7).
- Polygons with holes → multipolygon relations; multi-geometries exploded.
- Tags: `lm:l` (table), `lm:t` (objekttypnr) plus the theme attributes that the styles need
  (`lm:sk`, `lm:idx` for `stodkurva`, `ele`, `name`, `ref`, `lm:text:*` for text layout).
  The tag schema is versioned and documented in `docs/tag-schema.md`.
- Pre-processing that *is* geometry work (and therefore belongs here, versioned):
  - **overview features**: per type, dissolved and simplified polygons (forest, water,
    built-up, fjäll) and only index contours, tagged `lm:ov=yes`, for low zoom levels. Needed
    because `mark` and `hojdlinje` are cut at the 10×10 km grid (see data-inventory §1).
  - joining multi-part names (`textdelnr`) into one searchable name.
- County/municipality regions: `administrativ_grans` only has **lines**; regions are made by
  polygonising them (fallback: a small bundled list of county bboxes).

### 3.3 S2 – split

splitter with `--max-nodes` tuned (start 1.6 M), `--max-threads`, `--keep-complete`,
`--output=pbf`, mapid range per family. The produced `areas.list` is cached and reused
(`--split-file`) so tile ids — and therefore Garmin's map-segment ids — stay stable between
builds of the same region. Expected tile count for Sweden: ~100–300.

### 3.4 S3 – compile

mkgmap with `--style-file`, `--gmapsupp`, `--index` (search), `--lower-case`, encoding per
ADR-0005, `--family-id`/`--product-id` fixed per product, `--max-jobs`, copyright
"© Lantmäteriet". TYP text is compiled by mkgmap in the same run. Overlay additionally
`--transparent --draw-priority=…`. Output: `gmapsupp.img` (base) and
`gmapsupp-skoter.img` (overlay), or one combined file (configurable; decided after the
device test).

Java tools are pinned (mkgmap r4924, splitter r654 today) and fetched by
`lm-garmin tools fetch` with SHA-256 verification into the cache; CI caches them.

## 4. Translation: Lantmäteriet object types → Garmin

The full table (every `objekttypnr` of all 44 layers → Garmin type, level range, TYP
colour/pattern/icon, label rule) will live in `docs/translation-table.md` and is generated
from — and tested against — the style files, so it cannot drift. Principles:

- Use **standard Garmin types** where the device or search gives them meaning (water, contours
  0x20–0x22, roads 0x01–0x07, cities 0x0100–0x1100, POI groups 0x64xx/0x65xx/0x66xx);
  **extended types** (0x10000+) for everything else, fully defined in the TYP.
- Every Lantmäteriet type gets a rule; a CI test fails if an object type present in the
  fixtures/inventory has no rule ("no silent drops").
- Draw order in TYP: background land cover → wetland/terrain overlays (`sankmark`,
  `markframkomlighet`) → water → buildings; lines: contours under hydrography under roads.

Draft for the bulk of the map (colours from the reference raster, spike S8):

| LM layer / type | Garmin | Shown from (mkgmap resolution) | Style (TYP) |
|---|---|---|---|
| `mark` 2645 Barr- och blandskog | 0x50 | 18 (overview: dissolved) | `#D4EEB7` |
| `mark` 2646 Lövskog / 2647 Fjällbjörkskog | ext 0x10f01 / 0x10f02 | 18 | `#C7D9B3`? / `#DFF5D9` |
| `mark` 2640 Öppen mark / 2644 Kalfjäll | ext / 0x52 | 18 | `#FFFFEA` / `#FFFFF2` |
| `mark` 2642 Åker / 2643 Fruktodling | 0x4e / ext | 20 | `#FFF7A6` / + dots |
| `mark` 2636–2639 bebyggelse, industri | 0x01, 0x02, 0x03, 0x0c | 18 | `#D58B5B`, `#E6B28C`, `#F2CF9B`, grey |
| `mark` 2631–2634 water, 2635 glaciär | 0x28, 0x3c, 0x48, 0x3f, 0x4d | 16 (overview: by `vattenytaid`) | `#CBEAFF`, glacier white/blue |
| `sankmark` 2651 fast / 2652 våt | 0x51 / ext | 20 | horizontal orange / blue line pattern (legend) |
| `markframkomlighet` 1571/1572/1573 | ext | 22 | grey / green hatch / dot pattern |
| `hojdlinje` 5 m / 10 m, `stodkurva=Ja` | 0x20 / 0x22, label = `ele` | 23 / 21 | `#D06A08`, index contour wider |
| `hojdlinje` Gropkurva | 0x21 | 23 | ticked line if TYP allows, else dashed |
| `vaglinje` 1801–1811 | 0x01–0x07, 0x06 for streets | 16–22 by class | casing + fill as legend; `ref` = `vardvagnummer` |
| `ovrig_vag` 1623/1624/1628/1846/… | ext lines | 22 | legend dashes |
| `ovrig_vag` 1847/1848 in **base** map | ext line "marked winter trail" | 21 | legend red-violet dashed (overlay adds skoter state) |
| `hydrolinje` | 0x18 / 0x1f by width class | 21 | `#0080E6` |
| `byggnad` polygons | 0x13 | 23 | dark grey |
| `byggnadspunkt` 2045–2047 | ext point, 3 sizes | 23 | small squares (unrotated, see §5.4) |
| `textpunkt` Bebyggelse/Tätort | city 0x0100–0x1100 by `textstorleksklass` | by size class | searchable |
| `textpunkt` Terrängnamn / Hydrografi | 0x66xx / 0x65xx | 21–22 | searchable |
| `textlinje` | label-only ext line (transparent in TYP) | 21 | curved label along line |
| `hojdkurvstext` | dropped – contour labels come from `ele` | – | – |

### 4.1 Zoom levels

Base map levels (tuned against the device): `0:24, 1:23, 2:22, 3:21, 4:20, 5:18, 6:16`.
Levels 0–1 carry fine contours and labelled index contours. Levels 2–3 show unlabelled
index contours. Level 4 thins those contours to 100 m intervals and shows merged lake and
coniferous/mixed-forest polygons. Level 5 uses source lake and forest geometry, and level 6
retains the broadest features for the overview. Garmin chooses the displayed level on the device.

The integration tests enforce per-level object budgets on the decoded fixture maps. The
same check is available for the [50 km Tärnaby benchmark](benchmarks/README.md#decoded-object-budgets).
These counts measure the number of objects in a build; device redraw timings are measured
separately.

See [Lantmäteriet overview sources](overview-sources.md) for the Topografi 100
and 250 comparison builds and the plan for overview labels and search.

## 5. Style strategy

### 5.1 Styles as source
A style = mkgmap style directory + TYP text in `styles/<name>/`. `lm-garmin build --style X`
selects it. A new style starts as a copy of `topo50`. Nothing is edited in GUI tools; TYP is
generated/validated text compiled by mkgmap.

### 5.2 Colours, widths, patterns
Starting palette from the raster (spike S8, data-inventory). Line widths from the legend
(mm at 1:50 000 → device pixels; Montana 700: 480×800 px, 5"). Patterns (myr, fruktodling,
blockig mark) as 32×32 TYP bitmaps.

### 5.3 Text and labels
- `textpunkt`: one Garmin point per name; `textstorleksklass` → choice of type and TYP font
  size (Garmin has ~4 label sizes), `textlage` cannot be honoured exactly (Garmin places
  labels itself).
- `textlinje` (19.7 k – rivers, lakes, long features): label-only lines give curved labels.
- `Upplysningstext`/`Fjällupplysningstext` (e.g. "Förbjudet område för terrängfordon …"):
  only at the highest levels, not searchable.
- Encoding: see ADR-0005 (Unicode needed for 1 017 Sami names).

### 5.4 Things Garmin cannot do (accepted deviations)
- No rotated point symbols (1.56 M rotated building points): draw as unrotated small squares;
  option to emit tiny rotated polygons for size class 2–3 only, if the device test shows the
  cost is acceptable.
- No hill shading, no label halos control, no free label placement or rotation.
- Line patterns are bitmap-based, so dash lengths do not scale with zoom.

### 5.5 Comparing appearance
| Automated (CI on fixtures, locally on 50 km tiles) | Manual |
|---|---|
| Render decoded `.img` (S4 GeoJSON + TYP colours/draw order) to PNG at the raster's resolution for the same bbox; produce side-by-side and diff images | Desktop: QMapShack (renders `.img` + TYP) for quick visual checks |
| Classify reference raster pixels to nearest palette colour → per-class **IoU** for area classes (water, forest kinds, open, field, built-up, wetland, glacier) | Device: checklist per release (`docs/device-testing.md`): redraw time at fixed zooms, legibility, overlay toggle, search |
| Feature budget per level, label counts per level | Colours outdoors (screen in sunlight) |

Reference rasters are not in the repo (CC0 but large); the comparison runs where they exist
and is skipped otherwise. (Open question: commit small 5×5 km raster cut-outs for the
fixtures — they are CC0 and ~1–3 MB each.)

## 6. Snowmobile overlay (ADR-0004)

- Source: `ovrig_vag` 1847/1848 (all values of `skoterkorning_tillaten`) + `ledintressepunkt_fjall` 1836.
- Separate map family, `--transparent`, high draw priority, own TYP:

| `skoterkorning_tillaten` | Look (proposal, based on the LM legend) |
|---|---|
| Påbjuden | solid orange-red, wide, + 1836 symbol on points |
| Ja | solid orange, wide |
| Ingen information | dashed orange, medium |
| Nej | thin grey dashed with red ticks – clearly "not for snowmobiles" |

- Built as its own `lm-skoter.img`, independently switchable in *Map Manager*.
  An optional single-file bundle is tracked in [#51](https://github.com/nilande/lm-garmin/issues/51).
- Optional: a *third* map family built from a local OpenStreetMap extract, with OSM
  attribution and distinct line styles. Show complementary stretches where the data
  differs from Lantmäteriet's winter trails.
- Skoterleder.org GPX can be used for the optional local coverage comparison and is
  excluded from build inputs, CI and published artifacts. See [#2](https://github.com/nilande/lm-garmin/issues/2).

## 7. Search and routing

- **Search**: the default base map includes a town index. The v0.1 device check uses
  **Cities** with **LM Topo50** selected as the search map. Lake and mountain search
  passed in the diagnostic map. Production integration is tracked in
  [#16](https://github.com/nilande/lm-garmin/issues/16).
- **Routing** (not MVP): needs a connected network. Plan: road layers converted with shared
  nodes at identical coordinates (node de-duplication in S1 for `vaglinje`, later
  `ovrig_vag` 1847/1848 for winter routing), `mkgmap:road-class`/`road-speed` from vägklass,
  `--route`. The S1 tag schema already carries everything needed; only node sharing and
  style rules are added.

## 8. Performance

Measured in the spikes (M5, 10 cores, 16 GB): one 50×50 km tile ≈ 25 s end-to-end
(after extraction) with a naive XML intermediate; mkgmap peak 2 GB RSS; `.img` 6–11 MB per
2 500 km². Strategy:

1. Unpack once to SSD (S0); never read zips or the NAS in the hot path.
2. R-tree selection, no clipping; Arrow batch reads; vectorised reprojection.
3. PBF, not XML (XML for Sweden ≈ 50 GB).
4. Parallel: themes in S1 (process pool), splitter `--max-threads`, mkgmap `--max-jobs`.
5. Content-addressed cache per stage; style change ⇒ S3 only.
6. Every stage logs wall time, CPU time and peak RSS to `build-report.json`.

**Targets** (to be re-baselined after the first full run in M1):

| Build | Target | Stretch |
|---|---:|---:|
| All of Sweden, cold (from unpacked cache) | ≤ 45 min | ≤ 20 min |
| One county (e.g. Jämtland) | ≤ 5 min | ≤ 2 min |
| Style-only rebuild, all of Sweden | ≤ 15 min | ≤ 8 min |
| Peak memory | ≤ 8 GB | ≤ 4 GB |
| CI integration build (3 fixtures) | ≤ 60 s | ≤ 30 s |
| `gmapsupp.img`, all of Sweden | < 4 GB (FAT32) | < 2 GB |

CI tracks the fixture timings (median of 3) in a JSON artifact and comments when a step
regresses by > 25 % against `main` (runners are noisy; regressions are warnings, not failures).

## 9. Garmin Montana 700 constraints

| Constraint | What we know | Plan |
|---|---|---|
| File size | FAT32: 4 GB max per file | expect 0.5–1.5 GB for Sweden; build fails above 3.5 GB; option to split per region |
| Number of `.img` files | Newer Garmins load all `*.img` in `Garmin/` (internal and SD); reports conflict for some models | device test S6 (two base + two overlay files side by side) |
| Tiles per map | no documented limit for `.img` (the 500-tile limit is for KMZ Custom Maps) | Sweden ≈ 100–300 tiles; monitor |
| Unicode | some newer models reject unsigned Unicode maps; GPSMAP 66 reported OK | device test S6, ADR-0005 |
| Family/product ids | must be unique per map product | fixed ids, documented; avoid ids used by common OSM maps |
| Start-up and redraw time | grows with tile count and objects per view | object budget per level (§4.1), overview features, timed device checklist |

## 10. Test strategy

| Level | What | Where |
|---|---|---|
| Lint/format | ruff, ruff format; `javac` compile of ImgDump | CI |
| Unit | tag mapping, id ranges, region parsing, OSM writer (round trip with pyosmium), TYP generator, "every LM type has a rule" | CI |
| Integration | build all fixtures → `.img`; mkgmap/splitter exit 0; `.img` structure (tiles, TYP, MDR index present); decode with `ImgDump`; expected Garmin types present per fixture; label spot checks ("Lövlund", "Våjhtja") | CI |
| Snowmobile completeness (**gate**) | per `skoterkorning_tillaten`: decoded length = source length ± 1 %; all 1836 points present with correct type | CI on `skoter_730_51` + `fjall_727_51_05` |
| Snowmobile coverage (**metric**) | share of GPX within **50 m** (and 25 m) of decoded overlay lines; baseline 45.9 % / 42.5 % | locally with Skoterleder.org GPX (skipped if missing); CI with a hand-made track in `tests/data/tracks/` |
| Appearance | render + IoU per class vs reference raster | locally (and CI if raster cut-outs are approved) |
| Performance | timings/RSS per stage on fixtures | CI artifact + trend; full-Sweden benchmark manually per release |
| Device | checklist | manual, per release |

Fixtures are produced by `scripts/make_fixtures.py` from a delivery (documented provenance:
delivery id, date, bbox, command); three areas (data-inventory "Test areas").

## 11. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Montana rejects Unicode `.img` | Sami names shown wrong | device test first; fallback cp1252 with transliteration (č→c, ŋ→n, đ→d, ŧ→t) + full name in search? |
| Device slow with full Sweden | unusable | overview levels, object budgets, split product per region |
| mkgmap/splitter maintenance (small project, Java) | blocked upgrades | pin versions, keep ImgDump tiny, integration tests catch breakage |
| Raster reference built from Topografi 10 | false "differences" | compare per class (IoU), not pixel-exact; document known differences |
| Topografi 50 structure change announced for **2027-05-04** | converter breaks | tag schema isolates it; integration test on test data from LM's FTP when available |
| Licence of Skoterleder.org data | cannot use | keep strictly local, never in repo/CI artifacts |
| 10 km cut geometries | many objects, ugly overviews | overview features (dissolve) in S1 |

## 12. Milestones and issue outline

### v0.1 MVP

The [v0.1 MVP milestone](https://github.com/nilande/lm-garmin/milestone/7) covers
the nationwide Topografi 50 base map and the separate Lantmäteriet snowmobile
overlay. The release candidate uses Topografi 250 at resolution 18
(`--topo250-dir`) following the [Täby device retest](device-testing.md#täby-overview-retest).
The build command also supports Topografi 50 alone, an optional Topografi 100
overview and the optional direct OSM snowmobile supplement.

1. Build both Sweden files from a pinned `main` commit. Keep the cold
   Topografi 50 baseline and record the candidate sources, timings, memory,
   sizes, checksums and structural verification
   ([#11](https://github.com/nilande/lm-garmin/issues/11)).
   Check that the map families and tile IDs can coexist on the test device
   ([#3](https://github.com/nilande/lm-garmin/issues/3)).
2. Run the [Montana release checklist](device-testing.md#release-checklist) on those
   same files in Täby and Hemavan/Syter. Cover install, startup, redraw, map
   legibility, one town search and the snowmobile overlay in daylight
   ([#12](https://github.com/nilande/lm-garmin/issues/12),
   [#20](https://github.com/nilande/lm-garmin/issues/20),
   [#24](https://github.com/nilande/lm-garmin/issues/24)).
3. Record the results and resolve release-blocking failures before tagging `v0.1.0`.
   Release the code, styles and build instructions. Generated maps stay local.

Further style and overview work (#14–#16), additional encodings (#17), CI
trends and extra build tuning (#26–#27), routing (#28), packaging (#30) and the
single-file bundle (#51) follow v0.1.

### v0.2 Everyday map

v0.1.0 was released on 2026-11-20 ([CHANGELOG](../CHANGELOG.md)). The
[v0.2 milestone](https://github.com/nilande/lm-garmin/milestone/8) is about a map for
everyday use, driven by the Montana results. In priority order:

1. **Street names** ([#55](https://github.com/nilande/lm-garmin/issues/55)). Topografi 50 has
   none. Evaluate NVDB, Lantmäteriet address data and OSM (licence, coverage, matching to
   `vaglinje`), decide in an ADR, then implement it in a follow-up issue.
2. **Label priority and density** ([#16](https://github.com/nilande/lm-garmin/issues/16)):
   repeated reserve labels and dense labels at 2 km.
3. **Look** ([#14](https://github.com/nilande/lm-garmin/issues/14)): hatching against terrain,
   the 800 m street network, and the contrast of the light-orange overlay dashes
   ([#57](https://github.com/nilande/lm-garmin/issues/57) daylight check).
4. **Topografi 50 structure change on 2027-05-04**
   ([#56](https://github.com/nilande/lm-garmin/issues/56)): test against Lantmäteriet's test
   data and support the new structure in time.

Deferred until there is a need: routing (#28), packaging (#30), the single-file bundle (#51),
CI performance trends (#26) and further build tuning (#27). Each style change is tried with
a `--dev` map on the device before it is merged.

### Original milestones

M0–M5 retain the original breakdown by project area.

Labels: `type:feature`, `type:bug`, `type:chore`, `type:docs`, `area:pipeline`, `area:style`,
`area:skoter`, `area:ci`, `area:perf`, `needs-device`.

**M0 Foundations** — repo, licence, README, `.gitignore`, CI skeleton (ruff + pytest + Java),
`tools fetch` with checksums, `make_fixtures.py` + fixtures + provenance.

**M1 MVP base map** — S0 unpack/cache; S1 converter (PBF, Arrow, parallel themes, id ranges);
S2/S3 orchestration; region by bbox; minimal style covering every type; S4 ImgDump + structure
checks; integration test; first full-Sweden run and re-baselined targets; device smoke test.

**M2 Style** — translation table complete + doc generated from style; TYP palette and patterns;
zoom levels + overview features; text/labels (city types, textlinje, multi-part names);
Unicode decision (ADR-0005); appearance comparison tool; device checklist; county/municipality regions.

**M3 Snowmobile overlay** — overlay target; TYP per `skoterkorning_tillaten`; completeness gate;
coverage metric (local GPX + CI hand-made track); combined vs separate file option; device test.

**M4 Performance** — stage cache keys, style-only rebuilds, per-stage metrics in
`build-report.json`, CI perf trend, full-Sweden benchmark and tuning (`max-nodes`, jobs).

**M5 Later** — routing; OpenStreetMap supplement from a local extract; alternative styles; packaging.

## 13. Decisions (2026-11-18)

| Question | Decision |
|---|---|
| Repository | `nilande/lm-garmin`, public |
| Code licence | MIT (code, styles, TYP) |
| First device test area | Hemavan/Syter snowmobile area (E 500–550, N 7 250–7 310 km), then Stockholm NE |
| Skoterleder.org data | the site states its trails come from OpenStreetMap (see data-inventory). GPX stays local for coverage comparisons. The optional supplement reads directly from OSM (§6). |
| Coverage tolerance | report 50 m (primary, baseline 45.9 %) and 25 m (42.5 %); local check fails on a drop > 1 pp |
| MVP scope | searchable place names in, routing out |
| Third fixture | `skoter_730_51` added |
| Raster cut-outs | 1:50 000 cut-outs of the two raster-covered fixtures committed (`*.ref50k.tif`) |
| Language | code, docs and issues in English; README has a Swedish summary |
| Encoding | Unicode – Sami characters confirmed on the Montana 700 (ADR-0005) |
| Overlay delivery | separate `.img` file per map – several files load side by side and toggle independently; each needs its own tile-number range |
| Map texts | drawn as label points (`0x28xx`); POI types `0x65xx`/`0x66xx` show no labels on the device |
