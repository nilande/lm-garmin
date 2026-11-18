# Device testing – Garmin Montana 700

Results of tests on the real device. Newest first. The checklist for future releases is
issue #20.

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
