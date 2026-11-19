# Tag schema (version 2)

The converter (stage S1, `lm_garmin.convert`) writes Topografi 50 as OSM PBF. The OSM tags
only re-encode Lantmäteriet's own data ([ADR-0003](adr/0003-style-independent-intermediate-and-cache.md));
every presentation decision is made in the mkgmap style. The schema version is written to
the PBF header as `lm:tag-schema`.

## Files and ids

- One file per theme: `<theme>.osm.pbf` (13 themes, see `THEME_LAYERS` in `convert.py`).
- Ids are positive and ascending per object type. Theme number *i* (0-based, fixed order)
  uses ids in `[(i + 1)·10¹⁰, (i + 2)·10¹⁰)`, so all theme files can be given to splitter
  together without collisions.
- Order inside a file: all nodes, then ways, then relations.
- Nodes are not shared between features (no topology). Routing will need node sharing for
  road layers (issue #28).

## Geometry

| Lantmäteriet | OSM |
|---|---|
| POINT | tagged node |
| MULTILINESTRING | one tagged way per part |
| MULTIPOLYGON without holes | one tagged closed way per part |
| MULTIPOLYGON part with holes | `type=multipolygon` relation (tags on the relation) with untagged `outer`/`inner` ways |

Coordinates: EPSG:3006 → EPSG:4326 with PROJ, stored at 10⁻⁷° (≈ 1 cm). Features are
selected by the GeoPackage R-tree; geometries are **not** clipped to the region.

## Tags

| Tag | Source | Notes |
|---|---|---|
| `lm:l` | table name, e.g. `ovrig_vag` | always present |
| `lm:t` | `objekttypnr` | present on every table that has object types (not `textpunkt`, `textlinje`, `hojdkurvstext`) |
| `lm:<column>` | every other attribute | column name ASCII-folded (`alternativt_manér` → `lm:alternativt_maner`) |
| `name` | `textstrang` | text layers |
| `ele` | `hojdvarde` | contours and spot heights |
| `ref` | `vardvagnummer` | road number |
| `lm:ov` | derived lake geometry | `yes` on the merged lake and `detail` on its original fragments. Untagged lakes retain their source geometry at all levels supported by the style. |

Not carried: `fid`, `geom`, `objektidentitet`, `skapad`, `objekttyp` (redundant with `lm:t`).

Values: floats with no fraction are written as integers, other floats with at most two
decimals. Dropped values: empty, `Ingen information`, and `0` for `rotation`/`textriktning`.

> **A missing tag means "no information".** In particular, a winter trail (1847/1848)
> without `lm:skoterkorning_tillaten` has the value *Ingen information*; styles must handle
> that case explicitly.

For lake polygons (`mark`, type 2632), the converter can dissolve fragments
with the same `vattenytaid` within the selected region. A merged feature is added
only when the union is valid and reduces the number of polygon parts. It retains
the water-body identifier, holes and shoreline geometry. The default style uses
the merged geometry at resolution 20 and source fragments at the other levels.

## Example

```
way  lm:l=ovrig_vag  lm:t=1848  lm:skoterkorning_tillaten=Påbjuden  lm:vagutforande=Normal  lm:alternativt_maner=Nej
node lm:l=textpunkt  name=Staabrejohke  lm:textkategori=Hydrografi  lm:textstorleksklass=2  lm:textlage=1  lm:textriktning=22.18 …
way  lm:l=hojdlinje  lm:t=2401  ele=625  lm:hojdvarde=625  lm:stodkurva=Ja
```

## Changing the schema

Bump `SCHEMA_VERSION` in `tags.py` whenever a tag's meaning or presence changes; the stage
cache (issue #25) uses it to invalidate converted data. Never reorder `THEME_LAYERS`.
