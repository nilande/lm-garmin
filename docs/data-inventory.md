# Data inventory — Topografi 50 Nedladdning, vektor

Inventoried 2026-11-18 from the delivery `LM2026:173692` (data dated 2026-10-16),
product version **2026.05**. Generated with `spikes/01-inventory/inventory.py`
(full numbers in the tables below); narrative and findings written by hand.

No data is stored in this repository. See [README](../README.md) for how to get
the data from Geotorget.

## Sources

| What | Where |
|---|---|
| Product documentation (all themes, object types, attributes) | Geotorget → *Topografi 50 Nedladdning, vektor* → *Dokumentation*, also at `https://geotorget.lantmateriet.se/dokumentation/GEODOK/76/latest.html` (per-theme pages `…/informationsinnehall/tema-*.html`) |
| Legend for *Karta 1:50 000 Nedladdning, raster* (dated 2026-05-27) | `https://geotorget.lantmateriet.se/dokument/projects/karta-1-50-000-nedladdning-raster/released/2018.01/_scroll_external/attachments/37fe81cc7533/tf-karta-50000-raster.pdf` |
| Raster product documentation | Geotorget → *Karta 1:50 000 Nedladdning, raster* → *Dokumentation* (version 2018.01) |

## Markhöjdmodell Nedladdning, grid 50+ (terrain shading, #90)

Delivery `LM2026:176630` (2026-11-24), all of Sweden: 76 zips, 1.6 GB, plus `metadata/` with a
`<square>_metod.json` and `<square>_kvmfel.json` (GeoJSON) per square. Read by `dem.py`.

- One zip per **100 × 100 km** square, named `<N/100 km>_<E/100 km>.zip`: `71_5.zip` covers
  N 7 100–7 200 km, E 500–600 km (SWEREF 99 TM). Each holds one `.xyz` file.
- `.xyz`: one `x y z` row per point, space separated, **decimal commas**, heights in metres
  (RH 2000), two decimals. About 4 M points per full square.
- The `.xyz` files are dated 2015, so this is the *hdb* variant (older data, not updated)
  rather than the yearly *nh* variant. Checked on Geotorget on 2026-11-25: grid 50+ is only
  offered as *hdb* (höjddatabanken, last revised 2004). The newer laser-scanned model is
  *Markhöjdmodell Nedladdning* (1 m grid, COG, STAC API
  `https://api.lantmateriet.se/stac-hojd/v1`, terms for high-value datasets), not used yet.
- The points are about 50 m apart but **not on a SWEREF-aligned grid** (x and y have
  decimals and drift slightly, like a rotated grid). `dem.py` bins them into 50 m cells; in
  Storuman 0.02 % of the cells inside the data were empty and are filled from neighbours.
- Heights in the Storuman area: 247–1 905 m.
- Licence: **CC0**, as for Topografi 50 (Geotorget product page,
  `https://geotorget.lantmateriet.se/geodataprodukter/markhojdmodell-nedladdning-grid-50`).

> The PDF product descriptions linked in the original brief (`www2.lantmateriet.se/globalassets/…/e-pb-*.pdf`)
> return **404**. Lantmäteriet has moved all product documentation to Geotorget (HTML).

## Local layout

```
/Volumes/scratch/lm-kartdata/          (SMB share on a NAS – not a local disk)
├── LM2026:173692 - Topografi 50 Nedladdning, vektor/
│   ├── <tema>_sverige.zip   ×13        one GeoPackage per zip, all of Sweden
│   └── uttag.json                      GeoJSON; bbox axis order is wrong – use gpkg_contents
├── raster 1-50k/  72_5_50.tif, 65_6_55.tif (+ stray 62_6_55.tfw/.tab, see below)
├── raster 1-10k/  727_51_05.tif, 659_67_00.tif (+ .tfw/.tab)
└── snowmobile tracks/  nz8x138y65.gpx, nz8x139y65.gpx   (licence unknown – never commit)
```

Ignore `._*` (AppleDouble) and `.DS_Store` everywhere. Paths contain `:` , `,` and spaces – always quote.

## Measurements

| Step | Result |
|---|---|
| Sequential read from `/Volumes/scratch` (SMB) | **89 MB/s** (hojd zip, 1.97 GB in 22 s) – i.e. ~1 GbE |
| Unzip all 13 themes to local SSD (`~/.cache/lm-garmin/gpkg`) | ~99 s total (hojd 38 s, mark 44 s), 14 GB on disk |
| Full-table scans of all layers (count + group-bys), local SSD | ~65 s total; `hojdlinje` 33 s, everything else < 10 s |
| Clip 5×5 km of all 44 layers with `ogr2ogr -spat -clipsrc` | 5.7 s, 52 MB RSS → 1.5–3 MB GeoPackage |
| Select (no clip) 50×50 km of all 44 layers via R-tree | 17 s (fjäll) – dominated by 44 × `ogr2ogr` start-up |

Machine: Apple M5, 10 cores, 16 GB RAM, internal SSD with 341 GB free.

## Facts that differ from, or add to, the brief

1. **`mark` is one file, not 10×10 km files.** But the *geometries* in `mark`, `hojdlinje`
   (and probably `markkantlinje`/`sankmark`) are **cut at the 10×10 km index grid**: no
   `mark` polygon extends more than 10 km in either direction, and 274 k of 2.47 M polygons
   touch a 10 km grid line. Consequence: forests, lakes and contours are fragmented; this
   inflates object counts and must be considered when generalising for low zoom levels
   (merge by `vattenytaid` for water; dissolve by type for land cover).
2. **`stodkurva = Ja` is the index contour** ("redovisar var femte höjdkurva", drawn heavier):
   25 m in 5 m areas, 50 m in 10 m areas. 921 k of 4.7 M contours.
3. **Two contour equidistances**: `Höjdkurva5`/`Gropkurva5` (2401/2402) and
   `Höjdkurva10`/`Gropkurva10` (2404/2405, mountain area). Depression contours exist (116 k).
4. **`vaglinje.gatunamn` is empty for all 1.83 M features.** There are no street names in
   Topografi 50. Road numbers (`vardvagnummer`, 355 k) are available for shields.
5. **Text layer**: `textdelnr` 1/2/3 marks multi-part names (≈ 26 k pairs) – parts must be
   joined for search, but kept separate for placement. `textstrang` vs `karttext` hold the
   searchable string vs the cartographic string. `textlage` 1–9 is the anchor (keypad-style),
   `textriktning` is rotation in degrees, `textsparrning` letter spacing (only on lines).
6. **1 017 place names contain characters outside cp1252** (č 431, ŋ 332, Č 278, đ 141, ŧ 2)
   – all Sami names, concentrated in the mountains where the snowmobile overlay matters.
   A Latin-1 (cp1252) map cannot show them; see ADR-0005.
7. **Snowmobile objects (unchanged from the brief)**: `ovrig_vag` 1847 (1 985) and 1848 (7 863)
   with `skoterkorning_tillaten` ∈ {`Ja`, `Nej`, `Påbjuden`, `Ingen information`};
   `ledintressepunkt_fjall` 1836 (748). Over all of `ovrig_vag` the attribute is
   `Ingen information` for 505 k features, i.e. it is only meaningful on 1847/1848.
8. **Rotation**: points in `byggnadspunkt` (1.56 M, 93 % "Byggnad, storleksklass 1") carry a real
   `rotation`; most other point layers have `rotation = 0` everywhere. Garmin cannot rotate
   point symbols (see PLAN §5.4).
9. **The raster reference is not made from Topografi 50.** *Karta 1:50 000 Nedladdning, raster*
   is "framställd genom kartografisk generalisering av information från **Topografi 10**" and
   styled "så att den liknar den Topografiska webbkartan". Expect small geometric differences
   (and some objects in the raster that are not in Topografi 50) when comparing.
10. **The legend (2026-05-27) contains the snowmobile symbology**: *Färdväg vid skoteråkning*
    (orange dashed) and *Påbjuden färdväg vid skoteråkning* (orange solid with symbol), plus
    *Markerad vinterled* (dashed red-violet) and *Markerad sommar- och vinterled*.

## Test areas

| Name | Bbox (SWEREF 99 TM, m) | Size | Reference raster | Why |
|---|---|---|---|---|
| `fjall_727_51_05` | E 515 000–520 000, N 7 270 000–7 275 000 | 1.5 MB | 1:10 000 + 1:50 000 (`72_5_50`) | mountain, as in brief |
| `tatort_659_67_00` | E 670 000–675 000, N 6 590 000–6 595 000 | 3.1 MB | 1:10 000 + 1:50 000 (`65_6_55`) | urban + archipelago, as in brief |
| **`skoter_730_51`** (proposed) | E 510 000–520 000, N 7 300 000–7 310 000 | 3.0 MB | none (just north of `72_5_50`) | see below |

The fjäll tile from the brief contains only **3 winter-trail segments, all 1848/`Ja`**, and no
1836 points – too weak for the completeness test. A scan of all 5 km cells around the GPX
area found that the 10×10 km window **E 510–520 km, N 7 300–7 310 km** is the smallest that
contains **all 8 combinations** of 1847/1848 × `skoterkorning_tillaten` (52 segments) and
3 × 1836. It is inside the GPX bbox, so it also works for the local coverage check.

| `skoter_730_51` | Ja | Påbjuden | Nej | Ingen information |
|---|---:|---:|---:|---:|
| 1847 | 4 | 15 | 4 | 1 |
| 1848 | 8 | 11 | 4 | 8 |

## Reference rasters

All four are RGB, 8 bit per channel, LZW, 256×256 tiles, georeference embedded (SWEREF 99 TM).
`raster 1-50k/62_6_55.tfw/.tab` describe E 650–700 km, N 6 250–6 300 km and belong to no
file; `65_6_55.tif` has no side files – always trust the GeoTIFF's own georeference.

Dominant colours (from `spikes/08-palette`, half-resolution sample) – a starting palette:

| Colour | Share 72_5_50 | Share 65_6_55 | Probably |
|---|---:|---:|---|
| `#DFF5D9` | 24.0 % | – | Fjällbjörkskog |
| `#D4EEB7` | 17.4 % | 17.2 % | Barr- och blandskog |
| `#FFFFF2` | 16.0 % | – | Kalfjäll |
| `#CBEAFF` | 11.0 % | 20.3 % | Vatten |
| `#FFFFEA` | 4.0 % | 5.5 % | Öppen mark |
| `#FFF7A6` | – | 5.3 % | Åker |
| `#F2CF9B` | – | 5.3 % | Låg bebyggelse |
| `#E6B28C` | – | 1.3 % | Hög bebyggelse |
| `#C7D9B3` | – | 7.5 % | (Lövskog? / skogsmark med inslag – to verify) |
| `#D06A08` | 0.5 % | – | Höjdkurvor |
| `#0080E6` | 0.2 % | 0.2 % | Vattendrag, strandlinje |
| `#40BAFF` | 0.2 % | 0.2 % | Sankmark, våt (raster) |

The rasters are anti-aliased (220 k–400 k distinct colours), so automated comparison must
classify pixels to the nearest palette colour rather than match exactly.

## Snowmobile tracks (Skoterleder.org) – local only

287 tracks, 10 048 points, ≈ 1 118 km, no names or attributes, WGS84. Kept out of the repo
and out of every built map.

**Licence (2026-11-18, issue #2):** Skoterleder.org states on its "Om skoterleder.org" page
that the map is open, that anyone can contribute, and that it *gets its data from
OpenStreetMap*; the site's own code is open source (github.com/skoterleder/skoterleder.org).
The trail data is therefore OSM data under the **ODbL 1.0** ("© OpenStreetMap contributors").
Consequences:

- Using the GPX locally to measure coverage is fine.
- Committing the GPX, or shipping a map built from it, would require ODbL attribution and
  share-alike for the derived database. We still keep it out of the repo and CI.
- The optional supplement (issue #29) reads a local **OpenStreetMap** extract directly.
  This preserves the source tags and provides source attribution; GPX remains a reference
  dataset for checks. See the [OSM licence and attribution](https://www.openstreetmap.org/copyright).

### GPX export spot check near Syter (2026-11-19)

[Skoterleder.org](https://www.skoterleder.org/) describes its trail map as sourced from
OpenStreetMap and its GPX download as an export of the map. Its public
[GPX selection code](https://github.com/skoterleder/skoterleder.org/blob/8a165462a958fe94b678e4b54b283e00a552e817/website/js/skoterleder-ux.js#L980)
sends the selected area to a separate export service.

For a geometric spot check, OpenStreetMap way data was downloaded for the public bounding
box `15.24,65.82,15.52,65.94` (west, south, east, north). GPX tracks and tagged OSM ways
were compared within an inner window around Syter using length-weighted samples at up to
5 m spacing in SWEREF 99 TM. The outer window supplied nearby candidates at the edges.

| Comparison | Sampled length | Within 25 m | Within 50 m |
|---|---:|---:|---:|
| Skoterleder.org GPX → OSM | 27.89 km | 100.0% | 100.0% |
| OSM → Skoterleder.org GPX | 28.77 km | 97.2% | 97.5% |

This supports the stated OSM provenance for this export and window. The result is specific
to the sampled area and compares alignments in two snapshots. Only the aggregate figures
leave the local analysis.

## Structure change 2027.05 (from 2027-05-04, issue #56)

Lantmäteriet's *Produktförändringar våren 2027* changes Topografi 50 and 100 on
**2027-05-04**. Sources, read 2026-11-22:

- Product description **2027.05 (Kommande)**: Geotorget → *Topografi 50 Nedladdning, vektor*
  → *Dokumentation* → version 2027.05, static pages at
  `https://geotorget.lantmateriet.se/dokument/projects/topografi-50-nedladdning-vektor/released/2027.05/`
  (`Förändringsförteckning.html`, `Tema-Kommunikation.html`, `Tema-Höjd.html`).
- Test data: `https://www.lantmateriet.se/geodata_data/demodata_testdata/Testdata/Vektorrelease_2027/`
  (files dated 2026-11-03; Topografi 50 `hojd_ln01.zip`, `kommunikation_ln01.zip`,
  Topografi 100 `hojd_ln01.zip`; Stockholms län), archived locally in
  `/Volumes/scratch/lm-kartdata/Vektorrelease 2027 - testdata/` with `SHA256SUMS.txt`.
  Lantmäteriet: the test data shows the structure, but no data reflects the changes yet.

| Change (2027.05 description) | Test data (`ln01`) | lm-garmin |
|---|---|---|
| New layer `cykelvaglinje` (theme `kommunikation`): object type 1623 *Cykelväg*, attributes `objektidentitet`, `skapad`, `objekttypnr`, `objekttyp`, `bro_och_tunnel`; cycle paths come directly from Trafikverket | layer present, **0 features** | `THEME_LAYERS` (appended, ids unchanged), style row as for `ovrig_vag` 1623; `LAYERS_2027` in `convert.py` |
| `ovrig_vag` no longer holds 1623 *Cykelväg* | no 1623 | the old row stays for current deliveries |
| `hojdpunkt` 2412 *Triangelpunkt* renamed *Planpunkt* (GNSS point in the national reference network; number unchanged) | 79 *Planpunkt* | rule on 2412 unchanged, description "Triangelpunkt/Planpunkt" |
| `vaglinje` attributes: **unchanged** in the description (`vardvagnummer`, `gatunamn`, `cirkulationsplats` …) | **only** `objekttypnr`, `objekttyp`, `bro_och_tunnel` – the road numbers are missing | `build` warns and records `missing_columns` when the style reads a tag that no source column provides |
| Lake attribute in `mark` (news page) | – (no `mark` in the test data) | not in the 2027.05 change list for Topografi 50 |

Täby built from the test data (`hojd` and `kommunikation` replaced, other themes current):
all road-number labels (`0x01`–`0x0b`, 390 lines) and all 1 012 cycle-path lines are gone;
other features differ by under 1 % (the test data snapshot is from 2026-06). The road-number
gap contradicts the description; ask Lantmäteriet (geodatasupport@lm.se) before May 2027.
Topografi 100 `hojd` test data: same 2412 rename.

## Full table inventory

All layers: SRS 3006, R-tree index `rtree_<table>_geom`, geometry without Z/M.
Common columns `fid`, `geom`, `objektidentitet`, `skapad`, `objekttypnr`, `objekttyp` are
omitted from the attribute tables. "> 40 distinct" columns are free values.

### `hojd`

#### `hojdlinje` — MULTILINESTRING  4 697 449 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2401 | Höjdkurva5 | 4 159 868 |
| 2402 | Gropkurva5 | 113 801 |
| 2404 | Höjdkurva10 | 421 045 |
| 2405 | Gropkurva10 | 2 735 |

| attribute | type | values (count) |
|---|---|---|
| `hojdvarde` | TEXT(4) | >40 distinct  4 697 449 non-empty |
| `stodkurva` | TEXT(255) | `Nej` (3 776 107), `Ja` (921 342) |
| `i_glaciar` | TEXT(255) | `Nej` (4 682 492), `Ja` (14 957) |

#### `hojdpunkt` — POINT  33 801 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2411 | Markhöjd | 522 |
| 2412 | Triangelpunkt | 3 240 |
| 2413 | Höjdfixpunkt | 30 039 |

| attribute | type | values (count) |
|---|---|---|
| `hojdvarde` | MEDIUMINT | >40 distinct  33 801 non-empty |
| `rotation` | REAL | `0.0` (33 801) |

#### `hojdkurvstext` — POINT  387 157 features

| attribute | type | values (count) |
|---|---|---|
| `textkategori` | TEXT(255) | `Höjdkurvstext` (387 157) |
| `textstorleksklass` | TEXT(255) | `1` (387 157) |
| `textlage` | MEDIUMINT | `5` (387 157) |
| `texttyp` | TEXT(255) | `U` (387 157) |
| `karttext` | TEXT(4) | >40 distinct  387 157 non-empty |
| `textriktning` | REAL | >40 distinct  387 157 non-empty |

### `mark`

#### `mark` — MULTIPOLYGON  2 469 841 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2631 | Hav | 2 977 |
| 2632 | Sjö | 300 785 |
| 2633 | Vattendragsyta | 19 321 |
| 2634 | Anlagt vatten | 932 |
| 2635 | Glaciär | 333 |
| 2636 | Sluten bebyggelse | 393 |
| 2637 | Hög bebyggelse | 4 528 |
| 2638 | Låg bebyggelse | 16 547 |
| 2639 | Industri- och handelsbebyggelse | 6 994 |
| 2640 | Öppen mark | 1 334 357 |
| 2642 | Åker | 325 030 |
| 2643 | Fruktodling | 789 |
| 2644 | Kalfjäll | 11 495 |
| 2645 | Barr- och blandskog | 346 718 |
| 2646 | Lövskog | 62 304 |
| 2647 | Fjällbjörkskog | 35 589 |
| 2648 | Ej karterat område | 749 |

| attribute | type | values (count) |
|---|---|---|
| `vattenytaid` | TEXT(36) | >40 distinct  324 348 non-empty |
| `hojd_over_havet` | TEXT(20) | >40 distinct  24 959 non-empty |
| `reglerat_vatten` | TEXT(255) | `Ingen information` (2 469 367), `Ja` (474) |

#### `markkantlinje` — MULTILINESTRING  4 272 794 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2611 | Begränsningslinje  ej karterat område | 2 823 |
| 2612 | Strandlinje  hav | 105 124 |
| 2613 | Strandlinje  sjö | 779 858 |
| 2614 | Strandlinje  vattendragsyta | 130 631 |
| 2615 | Strandlinje  anlagt vatten | 1 625 |
| 2616 | Stängning mot hav | 181 |
| 2617 | Stängning | 15 233 |
| 2618 | Glaciärgräns | 369 |
| 2619 | Bebyggelseområdesgräns | 109 313 |
| 2620 | Industri- och handelsbebyggelsegräns | 26 011 |
| 2621 | Odlingsmarksgräns | 1 271 541 |
| 2622 | Öppen markgräns | 1 752 520 |
| 2623 | Skogsmarksgräns | 77 565 |

#### `sankmark` — MULTIPOLYGON  893 458 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2651 | Sankmark  fast | 806 389 |
| 2652 | Sankmark  våt | 87 069 |

#### `markframkomlighet` — MULTIPOLYGON  129 385 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1571 | Berg i dagen | 105 763 |
| 1572 | Tät vegetation  svårframkomlig | 3 922 |
| 1573 | Blockig mark | 19 700 |

### `kommunikation`

#### `vaglinje` — MULTILINESTRING  1 832 254 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1801 | Motorväg | 7 275 |
| 1802 | Motortrafikled | 1 150 |
| 1803 | Mötesfri väg | 20 363 |
| 1804 | Landsväg | 67 547 |
| 1805 | Landsväg liten | 230 665 |
| 1806 | Småväg | 198 066 |
| 1807 | Småväg enkel standard | 916 808 |
| 1808 | Övergripande länk | 7 055 |
| 1809 | Huvudgata | 52 110 |
| 1810 | Lokalgata stor | 24 706 |
| 1811 | Lokalgata liten | 306 509 |

| attribute | type | values (count) |
|---|---|---|
| `avfartsvag_pafartsvag` | TEXT(255) | `Ingen information` (1 819 791), `Ja` (12 463) |
| `cirkulationsplats` | TEXT(255) | `Nej` (1 822 022), `Ja` (10 232) |
| `bro_och_tunnel` | TEXT(255) | `Ingen information` (1 818 044), `Underfart` (12 803), `Tunnel` (709), `Överfart` (653), `Överfart och underfart` (45) |
| `gagata` | TEXT(255) | `Nej` (1 830 886), `Ja` (1 368) |
| `bussgata` | TEXT(255) | `Nej` (1 831 438), `Ja` (816) |
| `industrivag` | TEXT(255) | `Nej` (1 831 171), `Ja` (1 083) |
| `gatunamn` | TEXT(255) | `None` (1 832 254) |
| `vardvagnummer` | TEXT(255) | >40 distinct  354 930 non-empty |
| `gastvag1nummer` | TEXT(255) | >40 distinct  7 864 non-empty |
| `gastvag2nummer` | TEXT(255) | `None` (1 831 691), `47` (202), `E22` (76), `56` (50), `50` (48), `68` (37), `116` (36), `70` (25), `27` (20), `E20` (19), `562` (15), `124` (10) … |
| `alternativt_manér` | TEXT(255) | `Nej` (1 830 939), `Ja` (1 315) |

#### `vagpunkt` — POINT  135 245 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2203 | Väghinder | 52 542 |
| 2205 | Vändmöjlighet | 81 329 |
| 2207 | Rastplats | 322 |
| 2209 | Trafikplats | 1 052 |

| attribute | type | values (count) |
|---|---|---|
| `rotation` | REAL | >40 distinct  135 245 non-empty |
| `trafikplatsnummer` | TEXT(255) | >40 distinct  520 non-empty |
| `vaghindertyp` | TEXT(255) | `None` (82 703), `Låst grind eller bom` (52 542) |

#### `farjeled` — MULTILINESTRING  191 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1891 | Färjeled | 191 |

| attribute | type | values (count) |
|---|---|---|
| `destination` | TEXT(50) | >40 distinct  191 non-empty |
| `vagnummer_nationell` | TEXT(20) | `None` (127), `274` (7), `678` (6), `575` (6), `278` (6), `1036` (6), `751` (2), `665` (2), `623` (2), `975` (1), `907` (1), `891` (1) … |

#### `ovrig_vag` — MULTILINESTRING  513 518 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1623 | Cykelväg | 109 526 |
| 1624 | Gångstig | 150 803 |
| 1625 | Elljusspår | 14 743 |
| 1628 | Traktorväg | 202 593 |
| 1842 | Parkväg | 2 174 |
| 1846 | Vandringsled | 23 831 |
| 1847 | Vandrings- och vinterled | 1 985 |
| 1848 | Vinterled | 7 863 |

| attribute | type | values (count) |
|---|---|---|
| `vagutforande` | TEXT(255) | `Normal` (500 599), `Underfart` (6 821), `Bro` (6 034), `Tunnel` (53), `Sommarbro` (7), `Ingen information` (4) |
| `skoterkorning_tillaten` | TEXT(255) | `Ingen information` (505 295), `Ja` (4 413), `Påbjuden` (2 041), `Nej` (1 769) |
| `ruskmarkering` | TEXT(255) | `Ingen information` (512 582), `Ja` (931), `Nej` (5) |
| `alternativt_manér` | TEXT(255) | `Ingen information` (479 839), `Nej` (22 052), `Ja` (11 627) |

#### `transportled_fjall` — MULTILINESTRING  1 120 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1821 | Skidspår | 713 |
| 1822 | Lämplig färdväg | 27 |
| 1823 | Rennäringsled | 102 |
| 1824 | Fångstarm till led | 8 |
| 1825 | Roddled | 10 |
| 1826 | Svårorienterad gångstig | 235 |
| 1827 | Båtdrag | 1 |
| 1828 | Trafikerad båtled | 24 |

| attribute | type | values (count) |
|---|---|---|
| `rennaringsledstyp` | TEXT(255) | `0` (1 018), `Renflyttningsled` (90), `Renskötarled` (12) |

#### `ledintressepunkt_fjall` — POINT  2 894 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1832 | Vad | 95 |
| 1833 | Hjälptelefon | 112 |
| 1834 | Parkering | 127 |
| 1835 | Stormklocka | 1 |
| 1836 | Påbjuden färdväg vid skoteråkning | 748 |
| 1837 | Blinkfyr | 1 |
| 1838 | Gångbro  punkt | 1 810 |

| attribute | type | values (count) |
|---|---|---|
| `rotation` | REAL | >40 distinct  2 894 non-empty |
| `vagutforande` | TEXT(255) | `Bro` (1 808), `0` (1 055), `None` (29), `Sommarbro` (2) |

#### `ralstrafik` — MULTILINESTRING  13 161 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1861 | Järnväg | 12 039 |
| 1862 | Museijärnväg | 1 122 |

| attribute | type | values (count) |
|---|---|---|
| `bro_och_tunnel` | TEXT(255) | `Ingen information` (8 638), `Överfart` (2 504), `Underfart` (1 738), `Tunnel` (280), `Överfart och underfart` (1) |
| `under_byggnad` | TEXT(255) | `Nej` (12 088), `Ingen information` (818), `Ja` (255) |

#### `ralstrafikstation` — POINT  829 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1871 | Järnvägsstation | 829 |

| attribute | type | values (count) |
|---|---|---|
| `rotation` | REAL | `0.0` (829) |
| `status` | TEXT(255) | `Öppen` (791), `Ingen information` (33), `Avstängd` (4), `Ej underhållen` (1) |
| `under_mark` | TEXT(255) | `Ingen information` (816), `Ja` (8), `Nej` (5) |

### `hydrografi`

#### `hydroanlaggningslinje` — MULTILINESTRING  1 595 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1902 | Brygga | 365 |
| 1903 | Dammbyggnad | 832 |
| 1907 | Pir | 151 |
| 1910 | Vattentub/vattenränna | 244 |
| 1911 | Akvedukt | 3 |

#### `hydroanlaggningspunkt` — POINT  3 723 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1922 | Slussport | 295 |
| 1923 | Dammbyggnad  punkt | 3 428 |

| attribute | type | values (count) |
|---|---|---|
| `rotation` | REAL | >40 distinct  3 723 non-empty |

#### `hydrografiskt_intressant_plats` — MULTILINESTRING  7 721 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1583 | Fors | 7 681 |
| 1584 | Vattenfall | 40 |

#### `hydrolinje` — MULTILINESTRING  695 977 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1581 | Vattendrag | 695 977 |

| attribute | type | values (count) |
|---|---|---|
| `vattendragsid` | TEXT(36) | >40 distinct  695 968 non-empty |
| `storleksklass` | TEXT(255) | `1` (653 679), `2` (42 298) |
| `kanal` | TEXT(255) | `Nej` (695 887), `Ja` (80), `Ingen information` (10) |

#### `hydropunkt` — POINT  265 439 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1596 | Strömriktningspil  liten | 255 061 |
| 1597 | Strömriktningspil  stor | 10 378 |

| attribute | type | values (count) |
|---|---|---|
| `rotation` | REAL | >40 distinct  265 439 non-empty |

### `byggnadsverk`

#### `byggnad` — MULTIPOLYGON  91 195 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2061 | Bostad | 2 031 |
| 2062 | Industri | 17 212 |
| 2063 | Samhällsfunktion | 17 463 |
| 2064 | Verksamhet | 9 694 |
| 2065 | Ekonomibyggnad | 4 893 |
| 2066 | Komplementbyggnad | 38 857 |
| 2067 | Övrig byggnad | 1 045 |

#### `byggnadsanlaggningslinje` — MULTILINESTRING  1 600 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1978 | Lintrafik | 634 |
| 1980 | Renstängsel | 966 |

#### `byggnadsanlaggningspunkt` — POINT  14 717 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2019 | Mast | 12 777 |
| 2022 | Skorsten | 1 940 |

| attribute | type | values (count) |
|---|---|---|
| `hojd` | MEDIUMINT | `None` (14 591), `0` (125), `42` (1) |
| `rotation` | REAL | `0.0` (14 717) |

#### `byggnadspunkt` — POINT  1 558 667 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1042 | Kyrka | 3 362 |
| 1044 | Kåta | 832 |
| 1045 | Torn | 1 541 |
| 1046 | Vindskydd | 2 238 |
| 1047 | Väderkvarn | 683 |
| 1050 | Raststuga | 521 |
| 1051 | Fyrbyggnad | 150 |
| 1052 | Skyddsvärn | 20 |
| 2016 | Klockstapel | 501 |
| 2025 | Vindkraftverk | 5 933 |
| 2032 | Enslig stuga i fjällen | 605 |
| 2033 | Fjällstation | 11 |
| 2034 | Herrgård | 2 701 |
| 2035 | Kärnkraftverk | 4 |
| 2037 | Religiös byggnad | 140 |
| 2038 | Slott | 190 |
| 2041 | Turiststuga/övernattningsstuga | 117 |
| 2045 | Byggnad  storleksklass 1 | 1 455 553 |
| 2046 | Byggnad  storleksklass 2 | 50 669 |
| 2047 | Byggnad  storleksklass 3 | 31 839 |
| 2048 | Forskningsstation | 55 |
| 2049 | Hembygdsgård | 970 |
| 2050 | Naturum | 32 |

| attribute | type | values (count) |
|---|---|---|
| `hojd` | MEDIUMINT | `None` (1 558 663), `0` (4) |
| `rotation` | REAL | >40 distinct  1 558 667 non-empty |

### `text`

#### `textpunkt` — POINT  452 491 features

| attribute | type | values (count) |
|---|---|---|
| `textstrang` | TEXT(100) | >40 distinct  452 491 non-empty |
| `textkategori` | TEXT(255) | `Terrängnamn` (167 232), `Bebyggelse` (161 337), `Hydrografi` (95 712), `Upplysningstext` (17 392), `Skyddad natur` (4 381), `Tätort` (1 955), `Kyrka` (1 894), `Anläggningsområde/Byggnadsanläggning` (1 328), `Kulturhistorisk lämning` (1 012), `Fjällupplysningstext` (248) |
| `textstorleksklass` | TEXT(255) | `2` (323 126), `3` (74 132), `4` (24 841), `1` (21 311), `6` (3 512), `5` (2 768), `7` (1 769), `8` (590), `9` (266), `10` (176) |
| `textlage` | MEDIUMINT | `1` (174 071), `3` (98 023), `7` (69 404), `9` (46 222), `2` (45 159), `8` (6 539), `6` (5 457), `5` (4 395), `4` (3 221) |
| `texttyp` | TEXT(255) | `N` (434 202), `U` (18 289) |
| `textsparrning` | MEDIUMINT | >40 distinct  452 491 non-empty |
| `karttext` | TEXT(100) | >40 distinct  452 491 non-empty |
| `textdelnr` | MEDIUMINT | `0` (400 376), `2` (26 043), `1` (26 040), `3` (32) |
| `textriktning` | REAL | >40 distinct  452 491 non-empty |

#### `textlinje` — MULTILINESTRING  19 745 features

| attribute | type | values (count) |
|---|---|---|
| `textstrang` | TEXT(100) | >40 distinct  19 745 non-empty |
| `textkategori` | TEXT(255) | `Hydrografi` (18 357), `Terrängnamn` (1 170), `Upplysningstext` (188), `Skyddad natur` (15), `Fjällupplysningstext` (8), `Bebyggelse` (4), `Kulturhistorisk lämning` (2), `Anläggningsområde/Byggnadsanläggning` (1) |
| `textstorleksklass` | TEXT(255) | `2` (16 729), `3` (2 275), `4` (402), `6` (136), `1` (134), `7` (59), `8` (9), `9` (1) |
| `textlage` | MEDIUMINT | `1` (19 653), `3` (58), `7` (16), `9` (6), `2` (6), `4` (4), `6` (1), `5` (1) |
| `texttyp` | TEXT(255) | `N` (19 549), `U` (196) |
| `textsparrning` | MEDIUMINT | `100` (19 734), `140` (5), `135` (3), `130` (3) |
| `karttext` | TEXT(100) | >40 distinct  19 745 non-empty |
| `textdelnr` | MEDIUMINT | `0` (19 692), `1` (28), `2` (25) |

### `anlaggningsomrade`

#### `anlaggningsomrade` — MULTIPOLYGON  10 230 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2831 | Industriområde | 2 608 |
| 2832 | Samhällsfunktion | 5 769 |
| 2833 | Rekreation | 1 837 |
| 2834 | Civilt skjutfält | 16 |

| attribute | type | values (count) |
|---|---|---|
| `andamal` | TEXT(255) | `Skolområde` (3 231), `Täkt` (1 807), `Begravningsplats` (1 522), `Rengärde` (630), `Golfbana` (583), `Koloniområde` (444), `Avfallsanläggning` (411), `Ospecificerad` (393), `Motorsportanläggning` (393), `Vintersportanläggning` (306), `Sjukhusområde` (132), `Energiproduktion` (122) … |
| `skjutfaltstyp` | TEXT(255) | `None` (10 214), `Skjutfält` (10), `Skjutområde` (6) |
| `skjutfaltstext` | TEXT(100) | `None` (10 227), `ZON A` (1), `Utvidgad ZON A` (1), `Riskområde 10` (1) |

#### `anlaggningsomradespunkt` — POINT  18 244 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2841 | Industriområde  punkt | 223 |
| 2842 | Samhällsfunktion  punkt | 79 |
| 2843 | Rekreation  punkt | 10 183 |
| 2844 | Idrottsplan  punkt | 7 759 |

| attribute | type | values (count) |
|---|---|---|
| `andamal` | TEXT(255) | `Fotbollsplan` (4 794), `Badplats` (4 288), `Idrottsanläggning` (3 310), `Skjutbana  mindre` (2 111), `Campingplats` (1 064), `Småbåtshamn` (918), `Skjutbana` (744), `Gästhamn` (603), `Hamn` (223), `Sjöräddningsstation` (79), `Bollplan` (75), `Travbana` (33) … |
| `rotation` | REAL | >40 distinct  18 244 non-empty |

#### `flygplatsomrade` — MULTIPOLYGON  182 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2854 | Flygplatsområde | 182 |

| attribute | type | values (count) |
|---|---|---|
| `iata` | TEXT(3) | >40 distinct  52 non-empty |
| `icao` | TEXT(4) | >40 distinct  141 non-empty |

#### `flygplatspunkt` — POINT  68 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2852 | Helikopterplats | 68 |

| attribute | type | values (count) |
|---|---|---|
| `icao` | TEXT(4) | `None` (31), `ESJS` (1), `ESJM` (1), `ESJL` (1), `ESJH` (1), `ESJD` (1), `ESJB` (1), `ESJA` (1), `ESHZ` (1), `ESHY` (1), `ESHX` (1), `ESHV` (1) … |
| `rotation` | REAL | `0.0` (68) |

#### `start_landningsbana` — MULTIPOLYGON  206 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2853 | Start- och landningsbana | 206 |

| attribute | type | values (count) |
|---|---|---|
| `flygplatsstatus` | TEXT(255) | `I drift` (190), `Nedlagd` (16) |

### `naturvard`

#### `skyddadnatur` — MULTIPOLYGON  9 258 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 5603 | Nationalpark | 31 |
| 5604 | Naturreservat | 7 464 |
| 5605 | Naturminnesområde | 1 |
| 5606 | Djurskyddsområde | 1 384 |
| 5607 | Kulturreservat | 75 |
| 5608 | Naturvårdsområde | 303 |

| attribute | type | values (count) |
|---|---|---|
| `djurskyddstyp` | TEXT(255) | `Ingen information` (7 880), `Fågelskyddsområde` (1 340), `Sälskyddsområde` (31), `Djurskyddsområde` (6), `Säl- och fågelskyddsområde` (1) |

#### `naturvardspunkt` — POINT  1 801 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 5803 | Övrigt naturobjekt | 774 |
| 5804 | Naturminne | 1 027 |

| attribute | type | values (count) |
|---|---|---|
| `rotation` | REAL | `0.0` (1 801) |
| `ovrigt_naturobjektstyp` | TEXT(255) | `Ingen information` (1 750), `Grotta` (31), `Raukområde` (17), `Källa` (3) |

#### `naturvardslinje` — MULTILINESTRING  20 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 5641 | Naturreservat  linje | 20 |

#### `restriktionsomrade` — MULTIPOLYGON  123 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 5602 | Förbjudet område för terrängfordon | 80 |
| 5609 | Tält- och eldningsförbud | 4 |
| 5610 | Eldningsförbud | 1 |
| 5611 | Förbjudet område för terrängfordon  tidsbegränsat | 38 |

| attribute | type | values (count) |
|---|---|---|
| `informativ_text` | TEXT(200) | `None` (116), `Område med särskilda bestämmelser för eldning och tältning` (4), `Kommunalt regleringsområde för skoteråkning med lokala föreskrifter` (2), `Område med särskilda bestämmelser för eldning` (1) |
| `tidsbegransning` | TEXT(100) | `None` (85), `från 5 maj` (37), `20 april - 10 juni` (1) |

### `kulturhistorisklamning`

#### `kultur_lamning_linje` — MULTILINESTRING  428 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2501 | Fornlämning  mittlinje | 81 |
| 2502 | Fornlämning  större | 30 |
| 2503 | Ruin  kantlinje | 7 |
| 2504 | Ruin  mittlinje | 9 |
| 2505 | Gruvhål  kantlinje | 301 |

#### `kultur_lamning_punkt` — POINT  30 864 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 2511 | Fornlämning  stor upplysningssymbol | 13 551 |
| 2512 | Fornlämning  mindre | 9 197 |
| 2513 | Milstolpe | 5 105 |
| 2514 | Ruin | 239 |
| 2515 | Minnessten  stor upplysningssymbol | 359 |
| 2516 | Övrig kulturhistorisk lämning  mindre | 455 |
| 2517 | Gruvhål | 1 958 |

| attribute | type | values (count) |
|---|---|---|
| `rotation` | REAL | >40 distinct  30 864 non-empty |

### `administrativindelning`

#### `administrativ_grans` — MULTILINESTRING  981 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1561 | Sjöterritoriets gräns i havet | 62 |
| 1562 | Riksgräns | 29 |
| 1563 | Länsgräns | 202 |
| 1564 | Kommungräns | 675 |
| 1565 | Odlingsgräns | 13 |

#### `riksrose` — POINT  694 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 5121 | Riksröse | 694 |

| attribute | type | values (count) |
|---|---|---|
| `beteckning` | TEXT(64) | >40 distinct  694 non-empty |
| `rotation` | REAL | `0.0` (694) |

### `ledningar`

#### `ledningslinje` — MULTILINESTRING  13 220 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1702 | Kraftledning stam | 2 227 |
| 1703 | Kraftledning region | 9 056 |
| 1704 | Kraftledning fördelning | 1 924 |
| 1707 | Telefonledning | 13 |

#### `transformatoromrade` — MULTIPOLYGON  563 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1741 | Transformatorområde | 563 |

#### `transformatoromradespunkt` — POINT  2 581 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1742 | Transformatorområdespunkt | 2 581 |

| attribute | type | values (count) |
|---|---|---|
| `rotation` | REAL | `0.0` (2 581) |

### `militartomrade`

#### `militart_omrade` — MULTIPOLYGON  286 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 5501 | Militärt övningsfält | 140 |
| 5503 | Militärt skjutfält | 146 |

| attribute | type | values (count) |
|---|---|---|
| `mo_id` | TEXT(6) | >40 distinct  286 non-empty |
| `skjutfaltstyp` | TEXT(255) | `Skjutfält` (146), `None` (140) |
| `riskomrade` | TEXT(100) | `None` (286) |

### `norrapolcirkeln`

#### `polcirkeln` — MULTILINESTRING  1 features

| objekttypnr | objekttyp | count |
|---:|---|---:|
| 1881 | Norra polcirkeln | 1 |

| attribute | type | values (count) |
|---|---|---|
| `versiongiltigfran` | DATETIME | `2020-02-06T14:43:37.000` (1) |
| `lagesosakerhetplan` | REAL | `0.03` (1) |
| `lagesosakerhethojd` | REAL | `0.0` (1) |
| `ursprunglig_organisation` | TEXT(255) | `None` (1) |

