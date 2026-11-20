# Street names – source evaluation (issue #55)

Status: **evaluation done** (2026-11-20). Licence, content and a matching test in Täby are
done. Proposed decision: [ADR-0007](adr/0007-street-names-from-nvdb.md) (NVDB).

## Problem

Topografi 50 has a `gatunamn` column in `vaglinje`, but it is empty for all 1.83 M features
([data inventory](data-inventory.md)). In towns the map has a full street network without
names. Place search works; there is no street or address search.

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

## Next steps

1. Accept ADR-0007 (or revise it).
2. Implementation issue: `--nvdb-dir` (reads only the name layers, cached per region), matching
   with 15 m / 30° / share ≥ 0.5. Split Topografi 50 segments where the name changes, instead
   of dropping partly covered segments. Add the tag `lm:gatunamn_nvdb` (tag schema bump), road
   name rules in the style, a small CC0 NVDB fixture for the Täby fixture area, and an automated
   name check. Then a device check of label density at 250 m and 800 m, and of whether street
   names become searchable.
3. Västerbotten data is available for a check in a sparser area (Tärnaby, Storuman).
