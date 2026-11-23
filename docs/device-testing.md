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
- [ ] For a build with `--nvdb-dir`: at **120 m** or closer, check that streets carry NVDB
  names in **Täby / Ensta** and in **Falun centrum** (60.6065, 15.6355; Dalarna is read from
  the FileGDB) and that names follow the street where it changes name. At **250 m**, only
  the larger named roads should be labelled
  ([earlier result](#2026-11-21--street-names-from-nvdb-issue-60)). In **Map Manager →
  LM Topo50 → map info**, check that the copyright lists **Trafikverket (NVDB)** next to
  Lantmäteriet.
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
| NVDB street names in Täby and Falun; Trafikverket in map info | |
| Overlay toggle and 1836 marker | |
| Four statuses, brightness and lighting | |
| Screenshot files and follow-up issues | |

## Pending Montana checks

Enable one test map at a time. For each comparison, keep the same map centre and
orientation and include the scale bar in the screenshots. Use the pause menu to
capture the screens and keep the BMPs from `Garmin/scrn/` locally. Record the map
build, device firmware, scale and result here when a check is complete.

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

## 2026-11-23 – v0.3.0 Sweden release check (#71)

Montana 700, 25.70, profile Hike (Detail Normal, text sizes Small, zoom levels Auto), only
LM Topo50 and LM Skoterleder on. Files from `dist/sweden-v0.3.0` (`d09ea72`, see
[benchmarks](benchmarks/README.md)). Captures in `dist/montana-release/v0.3.0-release-check/`.
**Accepted.**

- Map info: *LM Topo50 – ©Lantmäteriet, Trafikverket (NVDB)*, *LM Skoterleder –
  ©Lantmäteriet*, one © each (`97`, `107`).
- Täby at 1.2 km, 300 m and 250 m (`127`, `136`, `266`): street names in the small line
  font, place names stay dominant, reserves and road shields as before.
- Falun at 90 m (`317`): street names from the Dalarna FileGDB extract.
- Storuman–Tärnaby–Syter (`430`–`466`): lake and mountain names are back (#79), contours,
  hatching and trails as in v0.2.
- Snowmobile overlay around Tärnaby and Hemavan at 1.2–5 km (`469`, `478`).
- *Zoom Levels › Street Label = Off* hides the street names, but only after the next zoom
  step: the device keeps the labels already drawn until it loads another zoom level
  (device behaviour, not the map).

## 2026-11-23 – what *Map Points* and *Land Cover* control (#81)

Montana 700, 25.70, profile Hike, 200 m. Kit `spikes/10-label-sizes/make_category_kit.py`
(`lm-labelcat.img`, family 5758, east of Täby, no TYP): A city points `0x0100`–`0x1100`,
B label points `0x2800`–`0x2806`, C geographic POIs `0x65xx`/`0x66xx` alone, D common POIs,
E named polygons (lake `0x3c`, forest `0x50`, park `0x17`, wetland `0x51`, glacier `0x4d`),
F named lines (contour `0x20`, stream `0x18`, river `0x1f`, trail `0x16`). Captures in
`dist/montana-release/v0.3-label-categories/`.

| Setting | A city | B label pt | C geo POI | D POI | E polygons | F lines |
|---|---|---|---|---|---|---|
| Baseline: text Small, zoom Auto (`87`–`91`) | labelled | labelled | icon, **no label** | icon, no label | labelled (not the park) | labelled |
| *Zoom Levels › Map Points = Off* (`116`–`125`) | – | – | **icons hidden** | **icons hidden** | – | – |
| *Zoom Levels › Land Cover = Off* (`143`–`154`) | – | – | – | – | **land polygons and their labels hidden**; lake stays | – |
| *Text Size › Map Points = None* (`198`–`208`), *Large* (`260`–`270`) | – | – | – | – | – | – |
| *Text Size › Land Cover = None* (`225`–`237`) | – | – | – | – | **labels of forest, wetland, glacier hidden**; lake label stays | **contour label hidden**; river label stays |
| *Text Size › Land Cover = Large* (`282`–`291`) | – | – | – | – | glacier label larger, others dropped for space | contour label dropped |

"–" = no visible change.

- City points and `0x28xx` label points – all place names and map texts on our maps – follow
  **none** of these settings; only *Detail* moves them.
- *Map Points* governs POI **symbols** (geographic and common POIs); their names are not drawn
  at any text size. So the unlabelled `0x65xx`/`0x66xx` search points are firmware, not a
  setting (AGENTS.md lesson holds).
- *Land Cover* governs land polygons and their labels, and the **contour labels**: text size
  None gives a map without contour numbers. Lake polygons and river labels are not land cover.
- With street names (*Street Label*, 2026-11-22) this gives three device-side switches for an
  activity profile: street names, contour labels and POI symbols, plus all land polygons.

## 2026-11-23 – activity profiles written from the computer (#81, #78)

Montana 700, 25.70. Captures and profile copies in `dist/montana-release/v0.3-profile-test/`.
Each activity profile is an XML file `Garmin/Profiles/<name>.gpf` on the USB volume; the
file name is the profile name (there is no name field inside).

| Step | Result |
|---|---|
| Edit `Hike.gpf` while Hike is the active profile, eject | **Lost.** The device keeps the active profile in memory and writes it back over the file – when a USB connection starts (file time = plug-in time) and when it switches to another profile. *Zoom Levels* and *Text Size* still showed the old values (`22`, `28`). |
| Copy `Hike.gpf` (edited) to a new `LMTest.gpf`, eject, *Profile Change › LMTest* | **Works.** The new profile appears and has the values from the file (`33`–`98`). |
| With Hike active, change one value in the inactive `LMTest.gpf` (`LandCoverText` 0 → 1), eject, switch to LMTest | **Works.** *Text Size › Land Cover* = Medium (`27`). |

So the computer can set up profiles, but only profiles that are **not active** when the device
is connected: the device reads a profile file when it switches to that profile, and saves the
active one from memory. Map Manager choices (`ImgSelectName` lists the maps switched off) come
along with the profile. macOS writes `._<name>.gpf` AppleDouble files next to edited
profiles; remove them so the device does not see them.

Consequence for #81 and #78: a tool can ship ready-made profiles (e.g. *LM Hike*, *LM Town*,
*LM Snowmobile*) as new `.gpf` files based on the device's own profile, and update them later
as long as another profile is active. Editing the active profile has to be done on the device.

## 2026-11-22 – street names switched off per activity profile (#81, #77)

Montana 700, 25.70, the v0.3 candidate `lm-topo50.img` (`--nvdb-dir`). Captures in
`dist/montana-release/street-label-zoom-off/`.

*Map Setup › Advanced Setup* offers two street-label settings per activity profile:

| Setting | Choices | Effect on our map |
|---|---|---|
| *Text Size › Street Label* (`StreetLabelText`) | Small, Medium, Large – **no None** (`52`) | none visible (TYP `FontStyle=SmallFont` wins) |
| *Zoom Levels › Street Label* (`StreetLabelZoom`) | **Off**, Auto, 5 m, 8 m, 10 m … (`70`) | **Off hides the NVDB street names**; Auto = 1, Off = 0 in the profile |

With *Street Label* zoom = Off, Täby at 500 m and 200 m (`153`, `173`) keeps town and
settlement names, road-number shields (E18, 262, E18.20), *Naturreservat* and contour labels;
only the street names are gone. *Map Points* and *Land Cover* text sizes do have a None
(`56`, `61`).

So a calm map and a town map need no separate builds: street names can be switched per
activity profile on the device. This answers the first test of #81 and makes the
street-name overlay (#77) optional rather than required.

## 2026-11-22 – lake and mountain names missing in the Sweden map

Montana 700, 25.70, the v0.3 candidate `lm-topo50.img` (`dist/sweden-v0.3-nvdb`, `--nvdb-dir`, Topografi 250). Captures in
`dist/montana-release/v0.3-labels-missing/`: Täby at 300 m and 150 m (`234`, `240`) look as
before; around Tärnaby–Hemavan at 800 m–1.6 km (`256`, `260`, `266`, `272`) villages and
road numbers show, but **no lake or mountain names**.

Cause: since `b3b45d7` (2026-11-21, #16, so already in v0.2.0) the `continue` of the
searchable `0x6500`/`0x6600` rows sat in the `order` column of `mapping.csv` (one comma
short). Every Hydrografi and Terrängnamn text stopped at its invisible search point and never
reached the `0x2800` label rules. Fixed by moving it to `options`; `stylegen.load` now rejects
a non-numeric `order`. Storuman build: `0x2800` labels at level 0 from 176 to 3 803
(Laxfjället, Norra Sytertoppen, Stenträsk, Juktån labelled again). **Device recheck
(Storuman dev map with the fix): lake and mountain names show.**

Device settings tried at the same time: *Text Size › Map Points* None → Small made no visible
difference on our maps (so the unlabelled `0x65xx`/`0x66xx` points are not explained by that
setting), and *Street Label* Medium → Small made no visible difference to our street names in
Täby (TYP `FontStyle=SmallFont` already sets them; captures `291`, `314`, `322` at 65–150 m in
`dist/montana-release/v0.3-labels-fixed/`).

Device settings during this and the earlier checks (profile *Hike*, *Map Setup › Advanced
Setup*): Detail = Normal; Text Size: Map Points = None, User Waypoints = Small,
Street Label = Medium, Land Cover = Small.

## 2026-11-22 – Sweden map with NVDB street names (#71)

Montana 700, firmware 25.70. Build `c732baf` (`lm-topo50.img` 1.88 GB, 410 tiles, NVDB
Betraktelsedatum 2026-11-17; `lm-skoter.img` unchanged from v0.2.0), installed with
`lm-garmin install` (verified copy, 13 min 55 s). Captures in `dist/montana-release/v0.3-nvdb/`.
**Works as intended**, with one style finding.

| Check | Captures | Result |
|---|---|---|
| Täby / Ensta, 120 m and 65 m | `217`, `226` | Streets named from NVDB (Sportvägen, Lindvägen, Djäknevägen …). |
| Falun centrum, 120 m and 60 m (FileGDB) | `279`, `282`, `286` | Streets named (Svärdsjögatan, Östra Hamngatan, Åsgatan …). |
| Täby, 800 m | `354` | Towns and road shields only, no street names. |
| Map info | `307` | "©© Lantmäteriet, Trafikverket (NVDB)": the device prints its own "©", so the message must not start with one. |
| Search, Cities | `394` | Vallentuna, SE, 8.97 km N. |

Finding: street labels use the device's default line font, which is larger and bolder than
the town labels (compare "Ensta" and "Falun"). They compete with place names, and where a
street changes name the labels do not fit, so the change is not visible. 

Dev build with `FontStyle=SmallFont` on the street-name types (captures in
`dist/montana-release/v0.3-small-font/`: `47`, `55` Täby at 120 m and 65 m; `84`, `86`, `94`
Falun at 120 m, 50 m and 180 m): name changes along a street now show (Ilervägen/Mårdvägen,
Svärdsjögatan/Kristinegatan), but street names look as large and bold as town and waypoint
labels. A second dev build with `DayCustomColor=#505050` on streets and `LargeFont` /
`NormalFont` on town and settlement points (`dist/montana-release/v0.3-grey/`: `32`, `44`)
looked **the same**. TopoActive Europe at the same place (`51`, `71`, `82`, `94`) draws
street names large and bold like our first build, but Täby larger and "Ella gård" in a
compact font.

### Label kit (`spikes/10-label-sizes`, 2026-11-22)

One small map (`lm-labelkit.img`, family 5759) near Täby, shown alone, night colours.
Captures in `dist/montana-release/labelkit/` (`80`–`133`, at 120 m and 50 m).

| Object | Result |
|---|---|
| City points `0x0100`–`0x0d00` | Same bold label for all types; only the dot shrinks |
| City points `0x0e00`–`0x1100` | Dot, **no label** |
| Label points `0x2800`–`0x2804` with TYP `FontStyle` Small/Normal/Large, `DayCustomColor` | Same small, thinner label for all: TYP font and colour are **ignored on points** |
| Road lines `0x01`–`0x13` without TYP | Same bold label (the default line font) |
| Lines with TYP `FontStyle` | **Honoured**: SmallFont clearly smaller, NormalFont = default, LargeFont larger |
| Line with `DayCustomColor` red | Not seen in night colours; with the grey dev build in day colours, streets stayed black |
| Streams, rivers (`0x18`, `0x1f`) | Small font by default; boundary and railway use the default line font |

Decision: street-name road types keep `FontStyle=SmallFont` (`font=small` in `mapping.csv`,
lines only); the grey colour and town fonts are dropped. The device offers no TYP control
over point labels, so the town–street hierarchy cannot be widened further from the TYP.

## 2026-11-21 – v0.2.0 Sweden release check

Montana 700, firmware 25.70. Release build `1a8f5d6` (`lm-topo50.img` 1.87 GB, 410 tiles;
`lm-skoter.img` 0.9 MB), installed with `lm-garmin install` (verified copy, 13 min 55 s).
Development maps removed from the device. Captures in `dist/montana-release/v0.2.0/`.
**Accepted** ("everything looks excellent").

| Check | Captures | Result |
|---|---|---|
| Täby / Ensta, 250 m | `59` | Streets, names, contours and reserve hatching as in the accepted dev maps. |
| Stockholm, 8 km | `72` | Main roads with upright shields (E4, E18, 73, 77, 268…), towns readable. |
| Tärnaby / Hemavan, 8 km | `158` | E12, lakes, reserves; calm overview. |
| Syterstugan, 250–600 m, overlay on | `226`, `255`, `280` | All trail statuses and the ringed 1836 markers visible; contour labels, "Vindelfjällens nr". |
| Search, Cities with LM Topo50 selected | `324` | Villages listed as "<name>, SE". Before selecting the map, entries with "SWE" came from another map on the device (TopoActive). |
| Search result on the map | `360` | Nedre Björknäs opens at the right place. |

| Record | Result |
|---|---|
| Build commit and device firmware | `1a8f5d6`, 25.70 |
| Enabled maps | LM Topo50, LM Skoter (dev maps removed) |
| Redraw and legibility, Täby and Hemavan/Syter | fast; legible at 250 m – 8 km |
| Search | towns, villages, lakes and mountains with LM Topo50 selected |
| Overlay | four statuses and 1836 marker visible |

## 2026-11-21 – search, reserve names and 2 km contours (#16, #14)

Montana 700, firmware 25.70. Dev map from PR #67. Captures in `dist/montana-search/2026-11-21/`.
Accepted.

| Check | Captures | Result |
|---|---|---|
| Search: Rönningesjön, Stolpaskogen (Täby) | `114`, `123` | **Found** under Geographic Points, with distance and direction. |
| Search: Norra Storfjället, Gakkervattnet (Hemavan) | `213`, `232` | **Found** (also Norra Sytertoppen, Lill-Gakkervattnet, Gakkerbäcken). Results with ", 1768 M" come from another map on the device. |
| Map at 110–400 m, Täby | `257`, `279`, `294`, `354`, `360` | No new icons or duplicate names from the search POIs. Reserve names read "Täby prästgårds nr", "Rinkebyskogens nr" in full. |
| Norra Storfjället, 2 km | `492` | The 100 m contours are thin; the mountain no longer turns dark. The dark band at the top is outside the dev map. |

## 2026-11-21 – snowmobile overlay outdoors, synthetic grid at Ensta (#57)

Montana 700, firmware 25.70, outdoors in daylight at Ensta, Täby. Dev map with the synthetic
grid from `scripts/make_overlay_testgrid.py`: eight trails (1847/1848 × four statuses,
labelled "1847 Ja" … at the north end), three 1836 markers on "1847 Påbj", and bands of
sankmark våt (south third) and fast (middle third), centred at 59.45398 N, 18.06204 E. The
script places the grid anywhere; build it together with the real data as a `--dev` map. Captures in `dist/montana-skoter/2026-11-21/` (250 m, 180 m, 80 m).

| Status | Look (v0.1) | Outdoors |
|---|---|---|
| Påbjuden | red 5 px, dark edge | clearly visible |
| Ja | orange 4 px, dark edge | clearly visible |
| Nej | grey 3 px dashes | hard to see, above all over wetland hatching |
| Ingen information | light-orange 3 px dashes | hard to see |
| 1836 marker | red 9 px square | lost on the red Påbjuden line |

**First change.** Nej and Ingen information as 5 px dashes with a dark edge row; the 1836
marker as an 11 px red square with a 2 px white ring.

**Recheck outdoors** (`dist/montana-skoter/2026-11-21b/`, 250 m and 180 m): the ringed 1836
marker is clearly visible. The dark edge on the dashes was **not drawn**: Garmin line bitmaps
have two colours (dash and gap), so a third edge colour is dropped. Nej and Ingen information
are now two-tone long dashes (10 px on, 6 px off, 5 px wide) with the gap filled in a dark
colour: Nej `#B4B4B4` / `#303030`, Ingen information `#FFB060` / `#7A3A00`.

**Third check outdoors** (`dist/montana-skoter/2026-11-21c/`, 180 m and 80 m): both
two-tone lines are clearly visible over built-up ground, firm wetland and wet wetland, and
easy to tell apart from each other and from the solid Ja and Påbjuden lines. The 1836
markers stay visible. This closes the daylight check of #57.

## 2026-11-21 – street network and reserve hatching (#14)

Montana 700, firmware 25.70. Dev map from PR #64. Captures in `dist/montana-look/2026-11-21/`.
Accepted ("looks fine").

| Area and scale bar | Captures | Observation |
|---|---|---|
| Täby 2 km, 1.2 km | `63`, `70` | The town reads as built-up area with the main streets; no grey mass of local streets. |
| Täby 650 m | `92` | Local streets appear, thin and light; the network is readable. |
| Hemavan / Vindelfjällen 2 km | `153` | The sparser green hatch leaves the terrain visible. The dark look at Norra Storfjället comes from dense 2 px index contours on steep slopes, not from the hatch – a candidate for later tuning. |

## 2026-11-21 – labels and road shields (#16, #62)

Montana 700, firmware 25.70. Dev map from PR #63 (first commit). Captures in
`dist/montana-labels/2026-11-21/`.

| Area and scale bar | Captures | Observation |
|---|---|---|
| Täby 650 m – 2 km, Tärnaby 300 m – 2 km | `61`, `71`, `82`, `107`, `116`, `160`, `178`, `202` | Road numbers are **upright boxes** (E18, 262, 265, 951, E4; E12, 1113, 1117). |
| Täby 600 m – 1.2 km | `71`, `82`, `107` | Village names have no dot; town names (Täby, Danderyd, Sollentuna) keep theirs. Split names and reserves are drawn once. Reserve names are cut at about 24 characters (*Rinkebyskogens naturrese*). |
| Täby 2 km | `116` | No church "Täby" next to the town. |
| Täby 110–300 m | `88`, `97` | Street names, shields and contour labels fit. |
| Search, *Cities* | `253` | Village names are found, but every result reads "<name>, ABC": mkgmap's default country abbreviation. |

**Assessment.** The tester found the map too busy overall for outdoor navigation, above all in
town. At 800 m–1.2 km (resolution 21) nearly every Topografi 50 name was drawn, at a much
larger size than on Karta 1:50 000. The next build thins names by `textstorleksklass`:
class ≥ 3 at resolution 21, ≥ 2 at 22, all at 23; church and reserve names from 22. In the
dev map this drops the labelled points at resolution 21 from 288 to 137 in Täby and from
511 to 306 around Hemavan. The country is set to Sverige/SE.

**Second check** (captures in `dist/montana-labels/2026-11-21b/`, Täby 150 m – 2 km, Tärnaby
400 m – 2.8 km). 2 km looked right; every closer zoom was still too busy, in Täby and around
Hemavan. The captures also give the device's zoom-to-level mapping: index contour labels and
reserve names appear at 400 m and at 800–900 m, so **650–900 m is resolution 22, 1.2 km is
21, 2 km is 20** – one step coarser than assumed. The thresholds move one step: class ≥ 4
from 2 km, class 3 from 650–900 m, class 2 plus church, reserve and information texts from
400 m, class 1 only at the closest zoom. Labelled points at resolution 22: Täby 266 → 137,
Hemavan 488 → 306; at 21: Täby 137 → 68, Hemavan 306 → 125.

**Third check** (captures in `dist/montana-labels/2026-11-21c/`). Hemavan looked about right
at every zoom. Täby was still on the busy side at 400 m – 1.2 km; most labels there are
district names (Ensta, Tibble, Täby park, Näsbypark, Enebyberg). The search list now shows
"<name>, SE" for the dev map; "ABC" entries come from the v0.1 map on the device and "SWE"
from another map. The converter now tags map texts inside built-up land cover
(`lm:i_bebyggelse`, tag schema 5), and place names there come one step later (class ≥ 5
from 2 km, 4 from 650–900 m, 3 from 400 m); information texts in towns only at the closest
zoom. Hemavan is unchanged. Labelled points in Täby: 650–900 m 137 → 107, 1.2 km 68 → 44,
2 km 67 → 43. Nationwide the tagging adds 1.8 s to the text theme.

**Fourth check – accepted** (captures in `dist/montana-labels/2026-11-21d/`, Täby 400 m –
2 km, Hemavan 1.2 km). The tester found the label density OK in both Täby and Hemavan.
Remaining from #16: reserve names longer than about 24 characters are cut by the device.

## 2026-11-21 – street names from NVDB (issue #60)

Montana 700, firmware 25.70. Dev map from PR #61 (`--area taby --area hemavan --dev
--nvdb-dir`, NVDB 2026-11-17), street names on every level where streets are drawn.
Captures are kept locally in `dist/montana-street-names/2026-11-21/`.

| Area and scale bar | Captures | Observation |
|---|---|---|
| Täby, 800 m | `62.bmp` | No street names (town streets start at resolution 20–21); place names and E18 as before. |
| Täby centrum, 250 m | `72.bmp` | Street names are legible but large and dense; they dominate the map at this scale. |
| Täby, 80 m and 70 m | `88.bmp`, `271.bmp` | Street names fit well and follow the lines. Norrortsleden shows its road number **265**. Index contour labels are visible. |
| *Where to?* menu | `179.bmp`, `186.bmp`, `188.bmp` | No address or street search: the menu has Recent Finds, Waypoints, Coordinates, All POIs, Cities and POI categories only. *Later finding:* *Addresses* appears only for maps with NET data (`--net`/`--route`), which this map lacks – see #72. |

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
| Address search | Not available – Topografi 50 has no addresses or street names (expected); the menu also needs a map with NET data (#72) |
| Place search (Lövlund, Enebyberg, Sätra) | **Works** |
| Redraw speed, colours | Fast and smooth; colours fine |
| Activity profile (Hiking vs Boating) | **No effect** on which label rows were drawn |

Details and kit descriptions: [spikes.md § S6](spikes.md#s6--device-test-kit-spikes06-device-test).

Decisions: ADR-0005 accepted (Unicode); overlay ships as its own file (ADR-0004); map texts
become label points (issue #16); tile-number ranges per map file (issue #3).
