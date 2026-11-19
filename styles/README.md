# Styles

A style is one folder with a **`mapping.csv`** – the single source of truth – from which
`lm-garmin style generate` writes the mkgmap rule files (`points`, `lines`, `polygons`,
`options`, `info`, `version`, `relations`) and the TYP source `typ/<name>.txt`. Generated
files start with a "GENERATED" header; never edit them by hand. A test fails if they are
out of date, and another if any Lantmäteriet object type has no row.

| Style | Product | Family id |
|---|---|---|
| `topo50/` | base map `lm-topo50.img` | 5750 |
| `skoter/` | snowmobile overlay `lm-skoter.img` | 5751 |
| `skoter-osm/` | optional OpenStreetMap supplement `osm-skoter.img` | 5754 |

`mapping.csv` columns:

| Column | Meaning |
|---|---|
| `kind` | `point`, `line`, `polygon`, or `drop` (deliberately not drawn – give the reason in `description`) |
| `layer`, `t` | Lantmäteriet table and `objekttypnr` (empty `t` = any type of the layer) |
| `condition` | extra mkgmap expression on the tags of [docs/tag-schema.md](../docs/tag-schema.md) |
| `type`, `resolution` | Garmin type and the most zoomed-out mkgmap resolution where it is shown. Extended types are `0x1TTSS` with `SS ≤ 0x1f` |
| `name` | label expression, e.g. `${ele}`, `${ref}` (default: `${name}`) |
| `description`, `colour`, `colour2`, `width`, `pattern`, `order` | TYP look: pattern `solid`, `solid-bitmap`, `dash`, `dot`, `label`, `stripe`, `hatch`, `dots`, `mottled`, `icon`, `none`; polygon draw `order` 1–8 |
| `options` | `continue` keeps matching later rules. For a line rule, `outline` also copies the layer and object type to inner rings of matching multipolygons. |

Rows are evaluated top to bottom; the first match wins. Lessons from the Montana 700
(docs/device-testing.md): labels are only drawn for city types (`0x0100`–`0x1100`) and
label points (`0x28xx`), not for `0x65xx`/`0x66xx` POIs.
