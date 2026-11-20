# Device testing – Garmin Montana 700

Pending Montana checks and results from past device tests. The release checklist is tracked
in [issue #20](https://github.com/nilande/lm-garmin/issues/20).

## Pending Montana checks

Enable one test map at a time. For each comparison, keep the same map centre and
orientation and include the scale bar in the screenshots. Use the pause menu to
capture the screens and keep the BMPs from `Garmin/scrn/` locally. Record the map
build, device firmware, scale and result here when a check is complete.

- [ ] **Combined test of overview polygons and labels** ([build notes](../spikes/09-overview-labels/README.md)).
  Compare the installed **LM Test referens** and **LM Test oversikt**. Each map
  contains both areas. Use the same centre for the before-and-after pair at each
  scale.

  | Area | Scale bar | Centre (latitude, longitude) | Look for |
  |---|---:|---|---|
  | Sytertoppen | 2 km | **65.89225, 15.27215** | Norra Sytertoppen and distinct open mountain terrain |
  | Tärnaby | 8 km | **65.81933, 15.27567** | Stor-Laisan, the larger wetlands and legibility of terrain names |
  | Täby–Vallentuna | 2 km and 8 km | **59.51056, 18.04693** | Vallentunasjön, built-up fill and main roads |

  Record the scale where the overview switches if it differs from the suggested
  scale, and note any obvious difference in redraw time.
- [ ] **Topografi 50 fallback around Tärnaby** ([PR #42](https://github.com/nilande/lm-garmin/pull/42)).
  At northern Stormyrtjärnen (**65.69294, 15.22104**) and **2 km**, compare the
  installed **Tarnaby myr fore** and **Tarnaby myr efter**. Check that the larger
  firm wetlands are still easy to recognize. This covers builds without
  Topografi 100.
- [ ] **Lake and mountain labels and search** ([issue #16](https://github.com/nilande/lm-garmin/issues/16)).
  Use the same **LM Test** maps. Compare results for Vallentunasjön and both
  distinct Stormyrtjärnen lakes, noting their positions. Try Norra Sytertoppen
  for mountain search and Vallentuna as the town-search control.
- [ ] **Snowmobile overlay contrast in direct sunlight** ([issue #24](https://github.com/nilande/lm-garmin/issues/24)).
  Check the physical display at normal riding brightness, especially the grey
  dashed routes against snow or open terrain.

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
