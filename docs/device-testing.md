# Device testing – Garmin Montana 700

Pending Montana checks and results from past device tests. The release checklist is tracked
in [issue #20](https://github.com/nilande/lm-garmin/issues/20).

## Release checklist

Use the same verified `lm-topo50.img` and `lm-skoter.img` for both
[#12](https://github.com/nilande/lm-garmin/issues/12) and
[#24](https://github.com/nilande/lm-garmin/issues/24).

- [ ] In **Map Manager**, enable **LM Topo50** and disable other detailed maps for
  the same area. Start with the snowmobile overlay off. Restart the device,
  record the time until the map is usable, and check that both LM products are listed.
- [ ] In **Täby / Ensta** (59.45393, 18.06203) and **Hemavan / Syterstugan**
  (65.89296, 15.39556), pan and zoom at **250 m**, **2 km**, and **8 km** or the
  closest scale shown. Record approximate redraw times. Check that roads and
  contours are legible close in, that major roads, lakes and relevant names
  remain identifiable in the overview, and that labels with diacritics render.
- [ ] Near Täby, open **Where To? → Cities** and choose **Select Map → LM Topo50**
  from the search menu. Find **Vallentuna** in the list or with **Spell Search**.
  The search-map setting is independent of **Map Manager**. Record which method
  worked and roughly how long it took.
- [ ] In daylight at normal brightness, enable the snowmobile overlay in
  **Map Manager**. At the [Syter example locations](#2026-11-19--snowmobile-overlay-issue-24),
  check the four line styles and the red 1836 marker at **180–250 m**. Toggle the
  overlay near Syterstugan and check that the base winter trail is still visible.

Record the build commit and firmware, the enabled maps, startup and redraw
times, search result, and the result of each overlay check. For any rendering
issue, take a screenshot from the pause menu with the scale bar visible and
note the location and display conditions. BMPs are stored under `Garmin/scrn/`.

Copy this record for each candidate.

| Check | Result |
|---|---|
| Build commit and device firmware | |
| Enabled maps and startup time | |
| Täby redraw and legibility at 250 m, 2 km, 8 km | |
| Hemavan/Syter redraw and legibility at 250 m, 2 km, 8 km | |
| Vallentuna search using LM Topo50 | |
| Overlay toggle and 1836 marker | |
| Four statuses, brightness and lighting | |
| Screenshot files and follow-up issues | |

## Pending Montana checks

Enable one test map at a time. For each comparison, keep the same map centre and
orientation and include the scale bar in the screenshots. Use the pause menu to
capture the screens and keep the BMPs from `Garmin/scrn/` locally. Record the map
build, device firmware, scale and result here when a check is complete.

- [ ] **Daylight check of the snowmobile overlay** (left open when v0.1.0 was released,
  [#24](https://github.com/nilande/lm-garmin/issues/24)). Outdoors at normal brightness, check
  that the four trail statuses and the 1836 marker are distinguishable at **180–250 m** near
  Syterstugan, in particular the light-orange *Ingen information* dashes over wetland hatching.
- [ ] **Labels and road shields** ([#16](https://github.com/nilande/lm-garmin/issues/16),
  [#62](https://github.com/nilande/lm-garmin/issues/62)). Dev map with the label changes.
  Check: road numbers as upright boxes (E18, 265 in Täby; E12 at Tärnaby) at 300 m, 800 m
  and 2 km; village names (e.g. Visinge, Lovisedal) without a green dot at 800 m; names
  such as reserves and split names (e.g. Vindelfjällens naturreservat) drawn once; no
  church "Täby" next to the town at 2 km. Village names must still be found under *Cities*.
- [ ] **Retest overview label priority after the next label build**
  ([issue #16](https://github.com/nilande/lm-garmin/issues/16)). Recheck
  Stor-Laisan at **8 km** and Vallentunasjön at **2 km** and **8 km**.
  Compare Swedish and Sámi name selection around Tärnaby. Use the centres in
  the [recorded comparison](#2026-11-20--combined-overview-polygons-and-labels).
  Time redraw separately if evaluating a performance change.
- [ ] **Topografi 50 fallback around Tärnaby** ([PR #42](https://github.com/nilande/lm-garmin/pull/42)).
  At northern Stormyrtjärnen (**65.69294, 15.22104**) and **2 km**, compare the
  locally archived **Tarnaby myr fore** and **Tarnaby myr efter** after reloading
  them onto the device. Check that the larger
  firm wetlands are still easy to recognize. This covers builds without
  Topografi 100.
- [x] **Lake search** ([issue #16](https://github.com/nilande/lm-garmin/issues/16)).
  Use **LM Test geo-POI**. In the category results, open the menu and choose
  **Select Map → LM Test geo-POI** before choosing **Spell Search**. Check this
  selection again after switching the displayed map in **Map Manager**. On the
  Montana, both the **Water Features** list and **Spell Search** returned one
  Vallentunasjön and two distinct Stormyrtjärnen locations.
- [x] **Mountain and town search** ([issue #16](https://github.com/nilande/lm-garmin/issues/16)).
  Select **LM Test geo-POI** as the search map. From Täby, use **Search Near**
  with a waypoint at **65.89220, 15.27149** before looking for Norra Sytertoppen
  under **Land Features**. Vallentuna appears under **Cities** near Täby.
- [ ] **Snowmobile overlay contrast in direct sunlight** ([issue #24](https://github.com/nilande/lm-garmin/issues/24)).
  Check the physical display at normal riding brightness, especially the grey
  dashed routes against snow or open terrain.

## 2026-11-21 – street names from NVDB (issue #60)

Montana 700, firmware 25.70. Dev map from PR #61 (`--area taby --area hemavan --dev
--nvdb-dir`, NVDB 2026-11-17), street names on every level where streets are drawn.
Captures are kept locally in `dist/montana-street-names/2026-11-21/`.

| Area and scale bar | Captures | Observation |
|---|---|---|
| Täby, 800 m | `62.bmp` | No street names (town streets start at resolution 20–21); place names and E18 as before. |
| Täby centrum, 250 m | `72.bmp` | Street names are legible but large and dense; they dominate the map at this scale. |
| Täby, 80 m and 70 m | `88.bmp`, `271.bmp` | Street names fit well and follow the lines. Norrortsleden shows its road number **265**. Index contour labels are visible. |
| *Where to?* menu | `179.bmp`, `186.bmp`, `188.bmp` | No address or street search: the menu has Recent Finds, Waypoints, Coordinates, All POIs, Cities and POI categories only. |

**Decision.** The Montana is mainly for navigation off-road, so street names are a bonus
for the detailed zoom. Karta 1:50 000 has no street names at all, and Karta 1:10 000 names
every street. Street names now appear only at resolution 23–24 (the levels that show index
contour labels, about 80 m and closer). Road numbers stay on every level. Street search is
not offered by the device's *Where to?* menu, so no search index is built for street names.

**Recheck with names at resolution 23–24** (same day, captures in
`dist/montana-street-names/2026-11-21b/`):

| Scale bar | Capture | Observation |
|---|---|---|
| 80 m, 120 m | `72.bmp`, `65.bmp` | All streets named and legible. |
| 250–300 m | `122.bmp` | The device already uses resolution 23 here (index contour labels show). It labels only the larger named roads (Turebergsvägen, Stockholmsvägen, Påtåkersvägen, Postvägen); small streets stay unlabelled. Accepted: a hierarchy like the raster maps. |
| 300 m and out | `122.bmp` | Road numbers (265, 873) follow the line, and which numbered roads are labelled varies. Upright shields and `--merge-lines` are tracked in [#62](https://github.com/nilande/lm-garmin/issues/62). |

## 2026-11-20 – v0.1 Sweden candidate

Montana 700, firmware 25.70. Used the [nationwide build from `1140add`](benchmarks/2026-11-20-build-sweden-v0.1-rc.json).
The tester reported response and loading times on the order of a second or a
few seconds. The session did not use timed individual measurements. Vallentuna
was found in the town search, and `313.bmp` shows the result selected.

| Area and scale bar | Captures | Observation |
|---|---|---|
| Täby / Stockholm, 800 m and about 2 km | `96.bmp`, `133.bmp`, `142.bmp` | Street hierarchy, shores and many names are readable. The 800 m street network and some 2 km labels are dense. |
| Täby / Stockholm, 5.6 and 8 km | `88.bmp`, `124.bmp` | Main roads and towns are readable. Irregular dark navy patches interrupt the land background. |
| Tärnaby area, 800 m and 2 km | `240.bmp`, `271.bmp` | Contours, roads, lakes and names with Sámi characters are visible. Repeated reserve labels and hatching compete with the terrain in the 2 km view. |
| Tärnaby area, 8 km | `212.bmp` | E12, Tärnaby, and the larger lakes are easy to follow. Dark exterior areas border the coverage, and smaller dark patches occur within it. |
| Syterstugan, 150, 200 and 600 m | `431.bmp`, `436.bmp`, `439.bmp` | The solid red required route is clear at all three scales. A small red square is visible southwest of the hut at 150 m. The 600 m view shows a short orange segment at the bottom-right edge. |

**Overview follow-up ([#15](https://github.com/nilande/lm-garmin/issues/15)).**
The navy inside the map matches the background colour outside coverage. A
decoded sample across Täby (17.99–18.18°E, 59.40–59.53°N) had Topografi 50 land
and water polygons over about 99% of the window at resolution 21 and 49% at
resolution 18. At resolution 18 the sample retains sea, lakes, and coniferous
and mixed forest. Built-up areas, open ground and fields account for most of
the missing fill.

### Täby overview retest

In matched-size Täby extracts, retaining more Topografi 50 classes at
resolution 18 increased land and water fill from 47.9% to 76.1% in the
sample window. Keeping smaller polygons in the compiler raised it to 84.8%
and produced 12,870 polygons across the extract. The Topografi 250 option
filled 95.3% with 1,979 polygons, compared with 3,397 in the original
Topografi 50 extract. The retest uses the official polygons at resolution 18.

The **8 km** Montana capture `56.bmp` shows the Täby–Stockholm area with
**LM Topo50 (dev)**. The large dark patches seen in `124.bmp` are largely
gone inside the common mapped area. Roads, towns, shoreline and open land
remain distinguishable. The dark band at the bottom is the edge of the
regional test map. The two views are slightly panned.

The device sample covers SWEREF 99 TM `630000,6540000,730000,6660000` and uses
Topografi 50 `LM2026:173692` with Topografi 250 `LM2026:174947`. The decoded
resolution-18 polygons cover 95.6% of the sample window above. The
[nationwide candidate from `70de4e1`](benchmarks/2026-11-20-build-sweden-v0.1-topo250.json)
uses the same sources and overview level. It was installed and checksum
verified as **LM Topo50**. The tester accepted the result.

### Overlay retest ([#24](https://github.com/nilande/lm-garmin/issues/24))

The matched Syterstugan views at **180 m** (`212.bmp` off, `223.bmp` on) show
the winter trail in the base map with the overlay off. Switching on
**LM Skoterleder** adds the red required route and the grey dashed stretch
near the hut. At **200 m**, `272.bmp` shows the solid orange permitted route
and the light-orange dashed route southwest of **65.84761, 15.33030**. The
light-orange dashes are visible and have lower contrast against wetland
hatching. The red 1836 marker is visible in the earlier `439.bmp`.

The tester accepted the result. A separate daylight check at normal
brightness has not been reported. See the
[known status locations](#2026-11-19--snowmobile-overlay-issue-24).

## 2026-11-20 – combined overview polygons and labels

Montana 700, firmware 25.70. Compared **LM Test referens** (family 5770) and
**LM Test oversikt** (family 5771) from the
[combined test build](../spikes/09-overview-labels/README.md). The captures
were slightly panned between maps. Comparisons use landmarks in their common
view. The dark surround at 8 km is outside the test-map footprint.

| Area | Scale bar | Target centre (latitude, longitude) | Observation |
|---|---:|---|---|
| Sytertoppen | 2 km | 65.89225, 15.27215 | The candidate draws additional terrain names. |
| Tärnaby–Hemavan | 2 km | 65.81933, 15.27567 | The candidate draws Norra Sytertoppen and Stor-Laisan. The reference shows Stoere Laajsere in the same lake area. |
| Tärnaby–Hemavan | 8 km | 65.81933, 15.27567 | E12, the larger lakes and the mountain areas are legible. The candidate draws Gakkervattnet and Stoere Vaerie. Stor-Laisan is encoded at this level and was absent from the screen. |
| Täby–Vallentuna | 2 km and 8 km | 59.51056, 18.04693 | The overview has a more continuous land background at 8 km. Main roads are clear in both maps. Vallentunasjön's label was absent at both scales, including in the candidate captures with the info banner closed. |

The file check confirms one candidate placement for Vallentunasjön and
Stor-Laisan per overview level. Their absence on the screen makes label
priority a follow-up for the next build. The Topografi 100 and 250 deliveries
contain Stor-Laisan and omit Stoere Laajsere. Retain verified Topografi 50
aliases where the coarse sources omit an official name as part of the next
label experiment. Redraw timings remain unverified.

In the subsequent search attempt, **All POIs** stopped responding. The user
reported finding other features under **Geographic Points → Water Features**
and no Vallentunasjön. In the two original test builds, Vallentunasjön is a
map label (`0x2800`), so the diagnostic now uses geographic POI types.

With the first diagnostic (**LM Test geo-POI**, family 5772), the device
listed Vallentunasjön in **Water Features** and opened it at the correct lake.
**Spell Search** stayed on the spinner during the test. The build has an
embedded MDR index with 5,507 point records. The next diagnostic (family
5773) uses the same encoding and has three indexed points. Both `LakeTest` and
`Vallentunasjön` were found by **Spell Search** after choosing the diagnostic
under **Select Map**. The screenshot shows **Spell Search** and **Select Map**
in the same menu. Changing the displayed map in **Map Manager** left the
search source unchanged on this device. With **LM Test geo-POI** explicitly
selected, the full-index diagnostic also returned the expected three lakes
through both paths. The two Stormyrtjärnen results opened different lakes, as
shown in the captures. Both builds and the screenshots are kept locally.

The follow-up found Vallentuna under **Cities** and Norra Sytertoppen under
**Land Features**. The mountain search took too long from Täby. Using **Search
Near** with a waypoint at the summit returned results near the waypoint. The
list also showed `Norra Sytertoppen, 1768 M` and `1768` nearby. The compiled
test map contains a named `0x6616` peak and a separate `0x6616` elevation point
labelled `1768`, about 75 m apart. The source of the combined name and elevation
entry was not established. Consider matching the named peak and elevation
point when preparing searchable peaks for the base map.

The pale-blue polygons north of Visinge also appear in the Topografi 50 data
and the Karta 1:50 000 reference. The saturated cyan stroke next to the
position arrow at Ensta is absent from the compiled test map. The source of
this device overlay was not confirmed.

## 2026-11-19 – OSM line visibility and the Täby diagnostic overlay

At Forsavan, the original designated OSM line (`0x10c00`) appeared at 200 m
and disappeared at 250 m, including with the other maps disabled. A continuous
bitmap alone did not change that threshold. With the same bitmap and geometry
but Garmin line type `0x10e0f`, the line appeared at 250 m.

Build a reusable side-by-side test of line types without any source map data:

```bash
uv run python scripts/build_line_diagnostics.py
uv run lm-garmin install dist/line-diagnostics/taby-testlinjer.img
```

Enable **Täby syntetiska testlinjer**, centre the map at **59.45393, 18.06203**
(Ensta), and keep north up. For a visibility comparison, disable the other
maps and take one screenshot per scale at 200 m, 250 m and 600 m. The rows
use equal-length lines at the same encoded zoom levels, numbered north to south:

| Row | Type | Style |
|---|---|---|
| 1 | `0x10c00` | Solid teal, original OSM code |
| 2 | `0x10e0f` | Same solid teal bitmap, revised OSM code |
| 3 | `0x10c01` | Dashed teal |
| 4 | `0x10c02` | Dotted teal |
| 5 | `0x10e14` | Solid orange, Lantmäteriet overlay |
| 6 | `0x10e16` | Dashed grey, Lantmäteriet overlay |
| 7 | `0x04` | Purple standard road type as a reference |

On the Montana 700, all seven lines appeared at 200 m. At both 250 m and
600 m, row 1 (`0x10c00`) was absent and rows 2–7 were visible. At 600 m,
the device hid several labels. The two teal solid rows use identical geometry
and bitmap styling apart from their positions and type codes.

## 2026-11-19 – snowmobile overlay (issue #24)

The paired 250 m screenshots at Syterstugan confirmed that the development
overlay toggles independently. The solid red overlay disappears when it is
disabled and the base map's trail remains. A red 1836 point symbol is visible
on the trail southwest of Syterstugan with the overlay enabled.

| Feature | Observed style | Example location (WGS84 latitude, longitude) |
|---|---|---|
| Påbjuden (required route) | Solid red line and a small red square | 65.88767, 15.38287 |
| Ja (permitted) | Solid orange line, easy to follow | 65.86460, 15.32363 |
| Nej (prohibited) | Dashed grey line, less prominent than the solid routes | 65.89296, 15.39556 near Syterstugan |
| Ingen information (no information) | Dashed light orange line, with the lowest contrast against the terrain patterns | 65.84761, 15.33030 |

All four styles could be identified in the 180–250 m screenshots. Readability
of the physical display in direct sunlight is still unverified.

## 2026-11-19 – raster-inspired style and zoom checks in Täby and Tärnaby

Built with `lm-garmin build --area taby --area hemavan --dev` and tested on the
Montana 700 with the development base map and snowmobile overlay enabled. The
comparison used the Lantmäteriet Karta 1:50 000 raster cut-outs for
[Täby](../tests/data/tatort_659_67_00.ref50k.tif) and
[Lövlund](../tests/data/fjall_727_51_05.ref50k.tif).

| Area and screen scale | Observed on the Montana 700 |
|---|---|
| Täby / Ensta, 35–300 m | Grey local streets and wider main roads are visible. The muted brown contour lines give the street network more contrast. |
| Lövlund / Nedre Björknäs, 180–400 m | Fine contours and index contour labels in metres are visible. Light green vegetation patches leave streams and paths legible. |
| Lövlund / Björknäsviken, 500 m | The fine contours and height labels disappear. Unlabelled index contours still show the terrain. The 10 km southward extension restores land coverage near Vojtjajaure chapel. |
| Stormyrtjärnen, 800–950 m | The orange snowmobile route and blue streams remain easy to follow. The dashed purple restriction boundary is visible. |
| Tärnaby / Gakkervattnet, 2–2.2 km | The sparser index contours leave more room for lakes, main roads and place names. The long terrain-vehicle notices are hidden at these scales. |

The scales above are the scale-bar readings on this device. The base style uses
resolution 23 and higher for fine contours, index contour labels and information
notices. Resolutions 21–22 show unlabelled index contours. Resolution 20 keeps
the index contours at multiples of 100 m.

On the Montana 700, take screenshots from the pause menu. The device saves BMP
files in `Garmin/scrn/`. Keep one centre point while changing scale and include
the scale bar in each capture to make before-and-after comparisons easier.

## Device facts (read from `GarminDevice.xml`, 2026-11-18)

| | |
|---|---|
| Model | Montana 700 (006-B3459-00), software 25.70 |
| Internal storage | FAT32 (`msdos`), 14 GiB, ~10 GiB free |
| Vector maps | `Garmin/*.img` – accepted as BaseMaps, SupplementalMaps, NMaps |
| Other map formats | `Garmin/CustomMaps/*.KMZ` (raster Custom Maps), `Garmin/BirdsEye/*.JNX` (BirdsEye raster), `Garmin/POI/*.gpi` |
| Largest installed map | TopoActive Europe East, one `.img` of 3.4 GB – our expected 0.5–1.5 GB for Sweden is well within what the device handles |

Idea for later (not planned): BirdsEye JNX could carry Lantmäteriet's 1:50 000 raster as an
exact-looking complement to the vector map.

## 2026-11-18 – first full-Sweden build (PR #33, issue #12)

`lm-topo50.img` (2.0 GB) and `lm-skoter.img` (0.9 MB) on internal storage. First impression:
"helt OK" – loads and is usable.

| Observation | Cause | Fix (branch `style/roads-contours`) |
|---|---|---|
| Gravel and country roads in Hemavan/Tärnaby clearly visible | standard road types `0x05`/`0x07` | – |
| Town streets in Täby **not visible** | 534 of ~570 street segments used extended types (`0x10d04` Huvudgata, `0x10d05` Lokalgata liten), and Lokalgata liten only showed on the three most detailed levels | all roads use standard Garmin road types (drawn even without TYP); streets from resolution 20–21 |
| Too much weight on contour labels | every 5 m contour was labelled | only index contours (stödkurvor) are labelled |
| Contour heights shown in **feet** | Garmin reads a contour label as feet. The label held metres, so "625" showed as 625 ft. The device uses a 12-hour clock (`Settings.fit`), so it probably also uses imperial units. | labels written in feet (`${ele|conv:m=>ft}`); a metric device then shows metres |
| Snowmobile overlay: clear, good line widths | – | – |

## 2026-11-18 – planning kits v2, v3 and label diagnostics (issue #1)

Device: Garmin Montana 700, maps on internal storage in `Garmin/`. Other maps present:
Worldwide DEM Basemap NR, TopoActive Europe East 2026.11.

| Question | Result |
|---|---|
| Several `.img` files side by side | **Yes**, each listed in *Map Manager*, as long as **every map has its own tile numbers** – a map with already-loaded tile numbers is skipped silently |
| Overlay on/off independently | **Yes** |
| Unicode (unsigned, from mkgmap) | **Loads**; á ŋ č Č đ ŧ display correctly on city and label points |
| Overlay styles (Påbjuden, Ja, Nej, Ingen information, 1836 points) | **All visible** once placed on all zoom levels (v3) |
| Labels on `0x650d` (lake) and `0x6614` (land feature) POIs | **Not drawn** (icon only) |
| Labels on `0x0c00` (city) and `0x2800` (label) points | Drawn |
| Address search | Not available – Topografi 50 has no addresses or street names (expected) |
| Place search (Lövlund, Enebyberg, Sätra) | **Works** |
| Redraw speed, colours | Fast and smooth; colours fine |
| Activity profile (Hiking vs Boating) | **No effect** on which label rows were drawn |

Details and kit descriptions: [spikes.md § S6](spikes.md#s6--device-test-kit-spikes06-device-test).

Decisions: ADR-0005 accepted (Unicode); overlay ships as its own file (ADR-0004); map texts
become label points (issue #16); tile-number ranges per map file (issue #3).
