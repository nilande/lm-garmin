# Garmin map IDs

Each map family installed on a Garmin needs its own family ID and a separate
range of tile IDs. Keep the production assignments in
[`products.py`](../src/lm_garmin/products.py).

| Map | Family ID | Tile numbering starts at |
|---|---:|---:|
| LM Topo50 | 5750 | 57500001 |
| LM Skoterleder | 5751 | 57510001 |
| LM Topo50 (dev) | 5752 | 57520001 |
| LM Skoterleder (dev) | 5753 | 57530001 |
| OSM Skoterkomplement | 5754 | 57540001 |
| OSM Skoterkomplement (dev) | 5756 | 57560001 |

Regional builds of the same product share its IDs. Install only one build of
each product at a time. The development outputs use separate IDs and can
coexist with their production equivalents.

## v0.1 candidate check

The Sweden build from `1140add` has 403 base tiles (57500001–57500403) and one
snowmobile overlay tile (57510001). The two files have distinct families and
tile IDs. Their IDs were checked against the installed TopoActive image (family
13545), the geo-POI test map (5772), and the Garmin basemap and time-zone map.
No tile or reported family IDs overlapped. The basemap and time-zone map had
readable tile directories and did not expose family IDs in MPS metadata.

Confirm that both LM products are listed and selectable on the Montana before
release. Other third-party map sets require their own compatibility checks.
