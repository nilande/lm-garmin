# Lantmäteriet data for Garmin overview levels

The detail map follows Karta 1:50 000. At coarser levels the aim is to make large
lakes, mountain areas, towns and main roads easy to identify. The Montana chooses
the displayed level. The scale-bar labels below are approximate.

| mkgmap resolution | Source for land cover, water surfaces and wetlands |
|---|---|
| 21–24 | Topografi 50 |
| 20 (around 2 km on the Montana 700) | Topografi 100 when supplied, otherwise Topografi 50 |
| 18 (next overview level) | Topografi 250 when supplied, otherwise Topografi 50 |
| 16 (widest overview) | Existing Topografi 50 rules |

Keep roads, trails, contours, place-search entries and other point features from
Topografi 50. Use Lantmäteriet's generalized polygons as a replacement at each
selected level. Topografi 100 retains separate firm and wet wetland classes and
mountain birch forest. Topografi 250 has a single wetland class and uses a coarser
selection of wetlands. Both have a single built-up class.
[Topografi 100 mark classes](https://geotorget.lantmateriet.se/dokumentation/GEODOK/54/latest/informationsinnehall/tema-mark.html)
· [Topografi 250 mark classes](https://geotorget.lantmateriet.se/dokumentation/GEODOK/56/latest/informationsinnehall/tema-mark.html)

## Comparison builds

Counts below are from compiled `.img` files for 50 × 50 km test areas. Each
pair used the same Garmin tile bounds. The reference includes the firm-wetland
rule tested in PR #42. The detail levels (24 through 21) and the widest overview
(16) matched by feature type, geometry and label in these builds.

| Test area (SWEREF 99 TM) | Resolution 20, Topografi 50 → 100 | Resolution 18, Topografi 50 → 250 |
|---|---:|---:|
| Tärnaby (`490000,7265000,540000,7315000`) | 11,943 → 9,576 polygons (−20%) | 2,148 → 472 (−78%) |
| Täby–Vallentuna (`650000,6570000,700000,6620000`) | 15,831 → 9,780 polygons (−38%) | 2,238 → 1,145 (−49%) |

At resolution 20, 136 of 137 representative points in 2–10 ha reference lake
polygons around Täby still fell in water. E4, E18 and route 265 followed the same
corridors. Built-up area grew from 309 to 373 km². At resolution 18, Topografi 250
adds about 602 km² of built-up polygons where the reference has no built-up fill
at that level. In Tärnaby, E12 stayed continuous at resolution 18. Its geometry
shifted locally by up to 158 m between the two compiled overviews, even though
the road source was the same. These are geometry and object-count measurements.
The device check covers redraw, legibility and the zoom transitions.

## Names and search

Keep Topografi 50 as the source of indexed objects and keep its town selection
for the first implementation. The polygon builds above retain the existing
labels. In the next pass, try selected lake and mountain names from Topografi 100
at resolution 20 and Topografi 250 at resolution 18. Choose text categories and
size cutoffs per product. For example, Topografi 250 assigns size class 2 to
Stor-Laisan, Vallentunasjön and Norra Sytertoppen. Keep overview labels on their
assigned levels so they cannot add records to mkgmap's POI index, which reads
points at the most detailed level in the pinned version (r4924). Some devices
can find POIs outside the index, so check the actual Montana 700 results.
[mkgmap options](https://www.mkgmap.org.uk/doc/options)
· [Topografi 100 text](https://geotorget.lantmateriet.se/dokumentation/GEODOK/54/latest/informationsinnehall/tema-text.html)
· [Topografi 250 text](https://geotorget.lantmateriet.se/dokumentation/GEODOK/56/latest/informationsinnehall/tema-text.html)

For matching label placements, use the complete `textstrang`, feature category
and geographic context. `objektidentitet` differed between products for the
sampled features, and placements can move substantially between scales. Prefer
association with the same lake or terrain feature where possible. Keep distinct
places that share a name.

Before testing on the device, build a label comparison for Tärnaby and
Täby–Vallentuna. Decode the `.img` files to check the intended level for each
new label and compare the full set of points at the most detailed level.
Use Vallentunasjön to test duplicate label placements and the two
Stormyrtjärnen lakes to test preservation of homonyms. Record label counts and
check that the detailed town points match. Track the remaining visual and
search checks in the [Montana checklist](device-testing.md#pending-montana-checks).
