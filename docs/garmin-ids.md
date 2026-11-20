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

The v0.1 check covers the files on the test Montana 700. Compatibility with
other third-party Garmin maps requires checking the IDs of the installed maps.
