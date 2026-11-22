# Street names – source evaluation (issue #55)

Status: **implemented** (issue #60, 2026-11-21) as `lm-garmin build --nvdb-dir`. Decision:
[ADR-0007](adr/0007-street-names-from-nvdb.md) (NVDB, accepted). The evaluation (#55) is
kept below; the [implementation section](#implementation-issue-60) has the final method and
results and the device check.

## Problem

Topografi 50 has a `gatunamn` column in `vaglinje`, but it is empty for all 1.83 M features
([data inventory](data-inventory.md)). In towns the map has a full street network without
names. Place search works; there is no street or address search (that needs a map with
street data, see #72).

## Candidates

| Source | Licence | Names | Geometry | Delivery | Verdict |
|---|---|---|---|---|---|
| **Trafikverket NVDB** (Lastkajen) | **CC0 1.0** (Trafikverket data product specifications for Lastkajen data) | Street names (`Gatunamn`); the road network of all 290 municipalities is in NVDB | NVDB road links. Topografi 50/10 roads are derived from the same network (*Vägslag*). | Free account on [Lastkajen](https://www.trafikverket.se/lastkajen); downloads by county or nationwide | **Preferred** |
| Lantmäteriet **Topografi 10** | CC BY 4.0 **plus** [terms for high-value datasets with personal data](https://www.lantmateriet.se/globalassets/geodata/geodataprodukter/anvandningsvillkor_for_vardefulla_datamangder_pu.pdf): the user is data controller under GDPR, with purpose limits, EU/EEA processing and spot checks | `vaglinje.gatunamn` ("namn på gata – hämtas från Trafikverkets produkt Vägslag"), i.e. the NVDB names | Same `vaglinje` table and object types as Topografi 50, at 1:10 000 | Geotorget, by county, municipality or Sweden; product version 2026.05 (2027.04 announced) | Technically easiest, but the terms do not fit an open tool used by others |
| Lantmäteriet **Belägenhetsadress** | Similar terms with personal data | Address points and address areas, not road lines | Points | Geotorget | Not suitable for labelling road lines |
| **OpenStreetMap** | ODbL 1.0 | `name` on `highway=*`; good urban coverage, quality varies | Own road network, needs matching | Geofabrik extracts | Fallback for local builds only, like the [OSM snowmobile supplement](../README.md#add-the-optional-openstreetmap-snowmobile-supplement) |

Topografi 50 itself stays **CC0**. Adding NVDB (CC0) keeps every input CC0, so built maps
stay free to share. Topografi 10 would bring CC BY 4.0 attribution and GDPR obligations into
every build. OSM would bring ODbL (share-alike).

## How names would be attached

Topografi 50 roads are generalised from the same Vägslag/NVDB network that carries the
names, so geometric matching should work well:

1. Read NVDB street-name segments for the region (EPSG:3006).
2. For each Topografi 50 `vaglinje` segment of classes 1806–1811 (towns and small roads):
   candidate NVDB segments within a buffer (start at 15 m) and with similar bearing
   (±30°), scored by overlapping length.
3. Assign the name covering the largest share of the segment, if it covers ≥ 60 %.
   Otherwise leave the segment unnamed. Record ambiguous cases.
4. Write the name as a new tag (`lm:gatunamn_nvdb` → `name` in the style). Bump the tag
   schema. Roads with a road number keep `ref`.
5. Garmin: road names on road lines are drawn along the line by the device. Searchability
   of street names (address search) is a separate question; mkgmap needs city/region data
   for that.

## Matching test – plan (Täby dev area)

Use the `taby` area (E 665–680 km, N 6 585–6 600 km) and report:

| Metric | Target |
|---|---|
| Share of 1809–1811 segments (by length) with a name | ≥ 90 % |
| Wrong names in a manual sample of 100 segments (checked against Karta 1:10 000 raster `659_67_00`) | ≤ 2 |
| Segments with two competing names | reported |
| Runtime for the area / for Stockholm county | reported |

## Test data

Trafikverket NVDB from Lastkajen, *betraktelsedatum* 2026-11-17, SWEREF 99 TM, for Stockholms
län and Västerbottens län (GeoPackage and File Geodatabase). The delivery's
`Licensinformation.txt` states **CC0 1.0**. The zips are stored outside the repo with
checksums. The GeoPackage has 124 layers; street names are in **`NVDB_DK_O_20_Gatunamn`**
(128 233 segments in Stockholms län; fields `Namn`, `ELEMENT_ID`, start and end measure,
`DIRECTION`, `ROLE`, …; LineString Z). Other road names, for example on forestry roads, are in
`NVDB_DK_O_21_Ovrigt_vagnamn` (7 585 segments, with `Namnsattande_organisation`). Each
lan file is 1.4–2.2 GB unpacked. Only the name layers are needed.

## Matching test – result (Täby dev area)

`spikes/09-street-names/match.py`, Topografi 50 `vaglinje` against `NVDB_DK_O_20_Gatunamn`
in E 665–680 km, N 6 585–6 600 km: 9 151 road segments, 12 617 NVDB name lines,
**0.5 s**.

| Class | km | Named (by length), 15 m / 30° / 0.6 |
|---|---:|---:|
| 1809 Huvudgata | 128.6 | 97.6 % |
| 1810 Lokalgata stor | 99.8 | 97.2 % |
| 1811 Lokalgata liten | 823.5 | 86.6 % |
| **Town streets 1809–1811** | 1 051.9 | **89.0 %** (target 90 %) |
| 1804–1805 Landsväg (liten) | 32.3 | 85–87 % |
| 1801/1803 Motorväg, Mötesfri väg | 112.8 | 24–25 % (they carry road numbers, not names – expected) |

Sensitivity for town streets: buffer 20 m → 89.2 %; minimum share 0.5 → **90.0 %**;
buffer 25 m, 40°, 0.5 → 92.8 % but 2.3× more ambiguous segments. The result hardly depends on
the buffer, so the geometries agree well. Of the unnamed town-street length, 5.0 % has **no
NVDB name within 15 m**, likely unnamed access roads, parking and private roads. Another
6.0 % is partly covered, where a name changes along a longer Topografi 50 segment. 389 of
7 682 town segments (5 %) have a runner-up name covering ≥ 30 %.

Visual sample against the 1:10 000 raster (whose street names also come from NVDB/Vägslag):
2 of 5 sampled names confirmed on the map, none contradicted, and 3 could not be judged from
the crop. Too few to judge the error rate. The implementation issue needs an automated check.

Known spike bug: overlapping pieces of the same name could be counted twice (one share of
1.47). The production code must union per name before measuring.

## Implementation (issue #60)

Code: `src/lm_garmin/street_names.py`, called by the converter for `vaglinje` when
`--nvdb-dir` is given. It differs from the spike in three ways:

- **Local direction.** The spike compared the bearing of the whole Topografi 50 segment with
  the whole NVDB line, so curved roads lost names. Now each covered stretch is compared with
  the part of the NVDB line next to it (±30°). Crossing streets still do not count.
- **Union per name.** Covered stretches are projected onto the segment as intervals and
  unioned per name before measuring, so overlapping NVDB lines are not counted twice.
- **Split instead of drop.** Each stretch gets the name that covers it (the larger total
  cover wins where names overlap). Stretches under 30 m join a neighbour. One name covering
  ≥ 50 % names the whole segment; otherwise the segment is split where the name changes and
  uncovered parts stay unnamed.

Both NVDB name layers are read: `NVDB_DK_O_20_Gatunamn` and `NVDB_DK_O_21_Ovrigt_vagnamn`
(forestry and other roads). Lines duplicated across county files are read once. The name is
written as `lm:gatunamn_nvdb` ([tag schema](tag-schema.md) version 4). In the style, roads
with a number (`ref`) are labelled with it on every level. Other roads of classes 1804–1811
get the street name at resolution 23–24 only (see the device check below). Motorways and
*mötesfri väg* (1801–1803) keep the number only.

### Quality check

`scripts/street_name_check.py` (local data, not CI) matches an area and checks (1) ≥ 90 % of
town-street length (1809–1811) named and (2) a seeded sample of 100 named town-street
pieces: 20 m in from each end, the nearest NVDB name line within 15 m must carry the same
name. At most 2 disagreements are allowed.

```bash
uv run python scripts/street_name_check.py \
  ~/.cache/lm-garmin/gpkg/kommunikation_sverige.gpkg /path/to/nvdb --area taby
```

Täby dev area, NVDB 2026-11-17 (2026-11-21):

| Class | km | Spike (0.6) | Implementation |
|---|---:|---:|---:|
| 1809 Huvudgata | 128.6 | 97.6 % | 98.5 % |
| 1810 Lokalgata stor | 99.8 | 97.2 % | 99.3 % |
| 1811 Lokalgata liten | 823.5 | 86.6 % | 95.4 % |
| **Town streets 1809–1811** | 1 051.9 | 89.0 % | **96.2 %** ✅ (≥ 90 %) |
| 1804 / 1805 Landsväg | 32.3 | 85–87 % | 91 / 96 % |
| 1806 / 1807 Småväg | 120.5 | – | 69 / 46 % |
| 1801 / 1803 Motorväg, Mötesfri väg | 112.8 | 24–25 % | 23–27 % (labelled with the road number) |

- Sample: **0 of 100** named pieces disagree with the nearest NVDB name at either end ✅.
- 265 of 9 151 segments were split where the name changes. 148 have two names over ≥ 30 %
  of their length (parallel streets, double names); the larger cover wins.
- Hemavan (Västerbotten): 37 % of 464 km road named. Mostly rural roads without NVDB
  names, as expected. Town streets in Hemavan: 83–100 %.

Runtime: 1.6 s for Täby. Stockholms län, as a bbox around the county: the `kommunikation`
theme takes 24 s instead of 6 s. The matching runs in that theme's worker, in parallel with
the other themes. The result is part of the convert stage, cached per region and NVDB checksum.

### Preparing NVDB for a build

Lastkajen offers street names only in the county packages (*Länsfiler NVDB-data*, one
GeoPackage and one FileGDB zip per county with the same content); the nationwide
*Sverigefiler utvalda NVDB-data* have only functional class, speed limit, surface, width,
road authority and the road network. `lm-garmin nvdb extract` reads the county zips one at
a time – GeoPackage zips are unpacked to a temp file, FileGDB zips are read in place
(layers `TNE_FT_Gatunamn_1` and `TNE_FT_Ovrigt_vagnamn_1`, name column `Namn_<n>`,
MultiLineStrings with M values) – and keeps the two name layers (name column, 2D) in one GeoPackage with a JSON
sidecar of sources, checksums and *Betraktelsedatum*. The date comes from the
`Leveransinformation_*.txt` in each GeoPackage zip; Lastkajen's FileGDB zips have no such
file, so those sources are dated `null`. `build` copies the dates into `build-report.json`
(`nvdb.betraktelsedatum`, and `nvdb.undated` for sources without one). Stockholms + Västerbottens län: 179 637 lines, 67 MB,
23 s; the Täby quality check gives the same result as with the full county files. All 21
counties (20 GeoPackage zips and Dalarna's FileGDB zip, Betraktelsedatum 2026-11-17, read
from a network share): 898 273 lines, 356 MB, 2 min 40 s; town streets named 96.2 % in Täby
and 91.0 % in Falun (from the FileGDB), 0 of 100 sample disagreements in both.

### Test data

`tests/data/nvdb/tatort_659_67_00.nvdb.gpkg` is a CC0 cut-out of both name layers (2 040
street-name lines, name columns only) for the `tatort_659_67_00` fixture, made by
`scripts/make_fixtures.py --nvdb-dir`. Unit tests (`tests/unit/test_street_names.py`)
cover parallel, crossing, overlapping, split, curved and ambiguous cases on synthetic
lines. The integration test (`tests/integration/test_build_street_names.py`) builds the
fixture with `--nvdb-dir` and checks that decoded town streets carry NVDB names.

### Device check (2026-11-21)

On the Montana 700 ([record](device-testing.md#2026-11-21--street-names-from-nvdb-issue-60)):
names were legible at 80 m but cluttered the map at 250 m. Karta 1:50 000 shows no street
names and Karta 1:10 000 shows all of them, so street names are now drawn only at resolution
23–24 (about 80 m and closer). Road numbers are drawn on every level. The device's *Where
to?* menu has no address or street search (only POIs, cities, waypoints and coordinates),
so no street index is built. *Correction (2026-11-21):* the Montana 700 does offer
*Addresses* and street routing, but only for maps with NET data (mkgmap `--net`/`--route`
and roads tagged as roads); street search is tracked in #72. A recheck confirmed the limit: at 250–300 m the device labels
only the larger named roads, and from 120 m all streets.
