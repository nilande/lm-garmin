# Street names – source evaluation (issue #55)

Status: **evaluation in progress** (2026-11-20). The licence and content review is done. The
matching test in Täby is waiting for NVDB data (see [Next steps](#next-steps)).
Decision draft: [ADR-0007](adr/0007-street-names-from-nvdb.md).

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

## Next steps

1. **Data:** create a free Lastkajen account (requires a person; not done by the tool) and
   download NVDB street names (and the road network if names are a separate layer) for
   Stockholm county as GeoPackage or Shape. Record the package name, date and licence text.
2. Run the matching test above and record results here.
3. Accept or revise ADR-0007, then open an implementation issue: a `--nvdb-dir` build option
   like `--topo250-dir`, style rules, a CI fixture with a small NVDB cut-out (CC0 allows it),
   and a device check of label density.
