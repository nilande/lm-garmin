# Overview names and polygons on the Montana

This experiment produces two maps that each contain Tärnaby and Täby–Vallentuna.
**LM Test referens** uses Topografi 50. **LM Test oversikt** uses the official
overview polygons and selected lake and terrain labels at resolutions 20 and 18.
Both retain Topografi 50 at the detailed levels and for town labels.

## Build

Pass one pair of split PBF tiles per test area. The reference uses a Topografi 50
build and the candidate uses both overview sources. Each area needs matching tile
bounds. The two `.img` files use separate Garmin family and tile IDs.

```bash
uv run python spikes/09-overview-labels/build.py \
  --topo100-dir /path/to/topografi100/gpkg --topo250-dir /path/to/topografi250/gpkg \
  --area tarnaby 490000,7265000,540000,7315000 /path/to/reference.pbf /path/to/candidate.pbf \
  --area taby 650000,6570000,700000,6620000 /path/to/reference.pbf /path/to/candidate.pbf \
  --out dist/overview-names
```

The script writes `comparison.json` with the selected labels and checks that the
decoded points match at resolutions 24–21 and 16. The prototype uses the full
text string. It groups repeated lake names on a connected water surface together
and keeps the same name on separate lakes. It checks lake labels against the
water polygons. At resolution 18, an anchor within 100 m of a lake may move inside
the shoreline if the same named lake was matched in Topografi 100. Vallentunasjön
is one example. At that scale, lake labels are limited to lakes of at least 1 km².
Terrain labels prioritize higher text-size classes and can carry an important
nearby Topografi 100 name through to Topografi 250.

## File checks

- The 43,033 point records at the most detailed level match in type, label and
  coordinate. The other three detail levels and resolution 16 also match.
- The candidate contains one placement each for Stor-Laisan, Norra Sytertoppen
  and Vallentunasjön at both resolution 20 and resolution 18.
- Both maps retain the two Stormyrtjärnen detail points at separate locations.

Check rendering and search behavior using the
[pending Montana checks](../../docs/device-testing.md#pending-montana-checks).
