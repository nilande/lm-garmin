# Device testing – Garmin Montana 700

Results of tests on the real device. Newest first. The checklist for future releases is
issue #20.

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

## Pending – snowmobile overlay (issue #24)

Enable the development base map and toggle the development snowmobile overlay in
Map Manager. At Syterstugan, capture the same view at 250 m with the overlay on
and off. With the overlay on, use the locations below to check each style on the
screen outdoors. Coordinates are WGS84 in decimal degrees (latitude, longitude).

| Feature | Expected style | Example location |
|---|---|---|
| Påbjuden (required route) | Solid red line and a nearby red point symbol | 65.88767, 15.38287 |
| Ja (permitted) | Solid orange line | 65.86460, 15.32363 |
| Nej (prohibited) | Dashed grey line | 65.89296, 15.39556 near Syterstugan |
| Ingen information (no information) | Dashed light orange line | 65.84761, 15.33030 |

Check the required-route point and distinguish all four line styles at 180–250 m.
Record the device scale and daylight conditions with the screenshots.
