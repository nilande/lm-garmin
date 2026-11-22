# Spike results (planning phase, 2026-11-18)

Code under `spikes/` is **throw-away**: it exists to answer questions and is not
production code. Nothing in it is imported by the tool. Outputs (`*.gpkg`, `*.osm`,
`*.img`) are git-ignored.

Tools used: GDAL 3.13.3, OpenJDK 27, mkgmap r4924, splitter r654, Python 3.12 via uv 0.13.

## S1 – Inventory (`spikes/01-inventory`)

Plain `sqlite3` over every GeoPackage: counts, object types, value distributions.
Results in [data-inventory.md](data-inventory.md). Takes ~65 s on local SSD.

## S2 – Clip test areas (`spikes/02-clip`)

`clip.sh` = `ogr2ogr -spat … -clipsrc …` per layer into one GeoPackage.
5×5 km → 1.5–3 MB, ~6 s. `select.sh` (no `-clipsrc`, R-tree only) is what a production
extractor should do; geometric clipping of `hojd`/`mark` dominated the 50 km run (62 s vs 17 s).

**Finding:** the brief's fjäll tile has 3 winter-trail segments and no 1836 points. Proposed
third fixture `skoter_730_51` (10×10 km) covers all 8 combinations – see data-inventory.

## S3 – GeoPackage → OSM → mkgmap → `.img` (`spikes/03-mkgmap`)

**Question:** can a small test area be built all the way to an `.img` mkgmap accepts, with a
simple TYP? **Answer: yes.**

- `gpkg2osm.py` (~150 lines, pyogrio + shapely + pyproj) writes OSM XML with synthetic tags:
  `lm:l` (layer), `lm:t` (objekttypnr), `lm:sk` (skoterkörning), `lm:idx` (index contour),
  `name`, `ele`, `ref`. Polygons with holes → multipolygon relations.
- A mkgmap style (`style/lm`, `style/skoter`) maps only on those tags. TYP is a text file
  compiled by mkgmap itself – no GUI tools needed, so style and TYP are plain source.
- Base map: 3 tiles + TYP → `gmapsupp.img` in **0.8 s**.
- Overlay: separate family id, `--transparent --draw-priority=30`, own TYP.
- Base + overlay **can be combined into one `gmapsupp.img`** (two families) or shipped as two
  files.

Gotchas found:

| Problem | Fix |
|---|---|
| Names missing in `.img` | custom styles must set the label: `name=* { name '${name}' }` |
| All labels upper-case | `--lower-case` |
| TYP with `CodePage=65001` fails ("SEVERE … Exiting", no message) | TYP text file must itself be UTF-8 |
| splitter: "Node ids are not sorted" | write positive, ascending OSM ids |
| zsh does not word-split `$opts` | build scripts in bash/Python, never rely on shell splitting |

## S4 – Decode the built `.img` (`spikes/04-decode`)

**Question:** can the snowmobile completeness check run on the *built map*? **Answer: yes.**

mkgmap ships its own reader (`uk.me.parabola.imgfmt.app.map.MapReader`): points, lines,
polygons per level, with types and labels. `ImgDump.java` (single-file Java, run with
`java -cp mkgmap.jar ImgDump.java tile.img`) prints GeoJSON lines.

Round trip on `skoter_730_51` (level 0):

| Garmin type | `skoterkorning_tillaten` | Source length | Decoded length | Ratio |
|---|---|---:|---:|---:|
| `0x10e10` | Ja | 10 038 m | 10 043 m | 1.000 |
| `0x10e11` | Påbjuden | 11 570 m | 11 569 m | 1.000 |
| `0x10e12` | Nej | 3 667 m | 3 670 m | 1.001 |
| `0x10e13` | Ingen information | 2 670 m | 2 669 m | 1.000 |
| `0x11610` | point 1836 | 3 | 3 | – |

mkgmap merges adjacent segments (55 input ways → 25 lines), so **completeness must be
checked by length per type (± 1 %) and by point count, not by feature count.**

Labels: must look up `POIRecord.getNameLabel()` for POIs. Unicode labels decode correctly.

## S5 – Coverage against Skoterleder.org GPX (`spikes/05-coverage`)

Overlay built for the GPX bbox (E 470–595, N 7 240–7 320 km), decoded, and GPX sampled every
5 m against an STRtree of decoded lines.

| Tolerance | Share of 1 118 km GPX within tolerance |
|---:|---:|
| 10 m | 33.5 % |
| 25 m | 42.5 % |
| **50 m** | **45.9 %** |
| 100 m | 48.4 % |

The 50 m figure reproduces the brief's baseline (≈ 46 %) **on the decoded `.img`**, so the
check measures what is really on the device. The curve flattens after 25–50 m: what is left
is trails missing from Topografi 50, not positional offset.

## S6 – Device test kit (`spikes/06-device-test`)

Built for manual testing on the Montana 700 (not committed):

| File | Contents |
|---|---|
| `lmtest-latin-bas.img` | 3 test areas, cp1252, searchable index, family 5730 |
| `lmtest-latin-skoter.img` | transparent snowmobile overlay, cp1252, family 5731 |
| `lmtest-unicode-bas.img` | same, `--unicode`, family 5732 |
| `lmtest-unicode-skoter.img` | same, `--unicode`, family 5733 |

**Lesson from the first device run (2026-11-18):** a rebuilt kit gave the latin and Unicode
base maps the same tile numbers (5730000x). The Montana listed only three of the four maps
in *Map Manager* and silently skipped `unicode-bas`. **Every map file must use its own tile
numbers**, even across variants of the same product (`build2.sh` now uses 5730xxxx, 5731xxxx,
5732xxxx and 5733xxxx; issue #3 must define these ranges). The Unicode *overlay* did load,
which is a first sign that the device accepts unsigned Unicode maps from mkgmap.

**Device results, kit v2 (2026-11-18, Montana 700):**

| Check | Result | Cause / next step |
|---|---|---|
| Maps listed in *Map Manager* | 4 of 4 after unique tile numbers | – |
| Unicode maps load | yes (overlay and base) | ADR-0005 can likely default to Unicode; confirm ŋ on screen |
| Mountain names | shown, look right | `0x6614` |
| Lake names (`textpunkt` Hydrografi → `0x650d`) | **not shown** | labels are in the `.img` (decoded); the device does not label `0x650d` by default → kit v3 defines `0x650d` in the TYP |
| Overlay toggle | works | – |
| Overlay: red/orange (Påbjuden/Ja) | shown | – |
| Overlay: grey dashed (Nej), points 1836 | not seen | only on the two most detailed levels (resolution 21) → kit v3 puts the whole overlay on all levels |
| Address search | not available | expected: Topografi 50 has no addresses/street names; test name search for places and POIs instead |
| Redraw speed, colours | fast and smooth; colours OK | – |

Kit v3 (`build3.sh` → `Garmin-v3/`, Unicode only, family 5734/5735) tests the two fixes.

**Device results, kit v3:**

| Check | Result |
|---|---|
| Overlay on all levels: Nej (grey dashed), Ingen information, 1836 points | **shown** – fixed |
| Place search (Lövlund, Enebyberg, Sätra) | **works** (city types `0x0c00`/`0x0800`, `--index`) |
| Names with **á** (Gárddiejávrrie, Syterskalet, Sytertoppen) | shown – but the visible Gárddiejávrrie is probably the *Bebyggelse* name (`0x0c00`), not the lake (`0x650d`) |
| Names with **ŋ** (Aŋŋájávrrie, Aŋŋájávrmuörkkie, Áŋkárenluoktta, Aŋŋáblierieke) | **none shown**, neither lake nor mountain – hypothesis: the device font lacks ŋ and the whole label is dropped |
| Lake names (`0x650d`) with a TYP icon | still not seen |

Diagnostic map `diag/make_diag.py` → `Garmin-v3/lmtest-etiketter.img` (family 5736): a 4×7 grid
600 m apart, just east of Syterstugan (E 520.5–524.1 km, N 7 303.5–7 305.3 km). Rows = point
type (`sjo` 0x650d, `fjall` 0x6614, `ort` 0x0c00, `etikett` 0x2800), columns = characters
1 a, 2 á, 3 ŋ, 4 č, 5 Č, 6 đ, 7 ŧ. Labels read e.g. `fjall 3 Aŋŋá`.

**Device result, label diagnostic map:**

| Row | Type | Icon | Label |
|---|---|---|---|
| sjo | `0x650d` | yes (small blue/green circle) | **no** |
| fjall | `0x6614` | yes | **no** |
| ort | `0x0c00` | yes | yes – all 7, Sami characters correct |
| etikett | `0x2800` | no | yes – all 7, Sami characters correct |

Conclusions:
1. **Unicode works on the Montana 700**, including ŋ, č, Č, đ, ŧ → ADR-0005 accepted (Unicode, no
   transliteration).
2. The missing lake and mountain names were caused by the **point types**: the device does not
   draw labels for water/land-feature POIs (`0x65xx`, `0x66xx`) on the map, whatever the
   characters. The ŋ names were Hydrografi/Terrängnamn, so they vanished; the names that did
   show were *Bebyggelse* (city types).
3. Consequence for the style (issue #16): Lantmäteriet's map texts are drawn as **label points
   (`0x28xx`, no icon)**, like on the printed map. Searchability of non-place names must be
   checked separately (label points may not be in the search index; option: emit a second,
   searchable POI with an invisible TYP icon, or test TYP `FontStyle` on `0x65xx`/`0x66xx`).

Questions it answers: (1) does the Montana accept several `.img` files side by side in
`Garmin/`; (2) can the overlay be toggled independently; (3) are Unicode maps accepted
(some newer Garmin models refuse unsigned Unicode maps – reports conflict); (4) do the
TYP colours/patterns render; (5) does search find "Lövlund", "Våjhtja".

## S7 – Performance of the naive pipeline (`spikes/07-perf`)

One 50×50 km raster tile, all layers, XML intermediate, 10 jobs:

| Step | Stockholm NE `65_6_55` | Fjäll `72_5_50` |
|---|---:|---:|
| extract (`ogr2ogr` per layer) | 62 s (clip) | 17 s (R-tree select) |
| GPKG → OSM XML | 6 s, 377 MB RSS → 509 MB XML | 2 s → 223 MB XML |
| splitter | 11 s, 564 MB RSS, 4 tiles | 6 s, 2 tiles |
| mkgmap (10 jobs) | 5 s, 2.0 GB RSS | 3 s, 1.6 GB RSS |
| `gmapsupp.img` | 11.3 MB | 6.3 MB |

Extrapolation (to be replaced by a real measurement in M1): Topografi 50 is 15.3 GB; the
Stockholm tile used 158 MB of it. ~100 such tile-equivalents × ~25 s ≈ **40–60 min** for all
of Sweden with this naive approach; `.img` ≈ **0.5–1.5 GB** (well under FAT32's 4 GB).
XML for all of Sweden would be ~50 GB – production must write **PBF** and stream.

## S8 – Reference palette (`spikes/08-palette`)

Most frequent colours of the two 1:50 000 rasters → starting TYP palette (see
data-inventory). Rasters are anti-aliased; comparison must classify to nearest palette colour.

## S9 – Street names from NVDB (`spikes/09-street-names`, issue #55)

`match.py` matches Topografi 50 `vaglinje` to NVDB `NVDB_DK_O_20_Gatunamn` (buffer, bearing,
covered share). Täby: 90.0 % of town-street length named in 0.5 s. Results and next steps are in
[street-names.md](street-names.md).

## S10 – Label size kit (`spikes/10-label-sizes`, 2026-11-22)

`make_kit.py` builds one small map near Täby with every city point type, label points and
road and other line types, each labelled with its type and TYP setting (`FontStyle`,
`DayCustomColor`). Result on the Montana 700: TYP font size works on lines only; points
ignore it. Record and table in
[device-testing.md](device-testing.md#label-kit-spikes10-label-sizes-2026-11-22).
