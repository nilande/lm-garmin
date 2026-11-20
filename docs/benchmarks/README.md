# Benchmarks

Reference machine: Apple M5 (10 cores), 16 GB RAM, internal SSD; data on an SMB share (NAS).
Delivery `LM2026:173692` (data 2026-10-16).

## 2026-11-20 – Sweden candidate with Topografi 250 (issue #15)

Built `70de4e1` from the same Topografi 50 delivery with Topografi 250
`LM2026:174947` at resolution 18. The [build report](2026-11-20-build-sweden-v0.1-topo250.json)
records both inputs, stage timings and output hashes. Topografi 50 conversion
and the snowmobile overlay were reused from the baseline cache.

| Measurement | Result |
|---|---:|
| Build time with cache | 669.47 s (11 min 9 s) |
| Highest reported process RSS | 4,638.2 MB |
| Base map bytes | 1,892,188,160 |
| Base map tiles | 410 |
| Land and water fill in the Täby sample at resolution 18 | 95.4% (49.1% in the nationwide baseline) |
| Nationwide polygons at resolution 18 | 157,153 (319,767 in the baseline) |

Both files passed structural verification. The overlay SHA-256 matches
the baseline. The new base map reuses family
5750 with tile IDs 57500001–57500410. The separate development map and other
maps installed on the Montana use distinct IDs.

## 2026-11-20 – v0.1 Sweden release candidate (issue #11)

Built commit `1140add` with ten jobs and a cold stage cache, using the unpacked
Topografi 50 delivery. The [build report](2026-11-20-build-sweden-v0.1-rc.json)
includes the source identifier, output SHA-256 checksums and decoded results.

| Stage | Wall time | Reported peak RSS | Output |
|---|---:|---:|---|
| Convert | 579.53 s | 731.1 MB | 18,585,717 features |
| Split base map | 262.02 s | 2,863.5 MB | 403 tiles |
| Compile base map | 444.17 s | 4,574.9 MB | `lm-topo50.img`, 1,894,350,848 bytes |
| Extract, split and compile overlay | 4.11 s | 314.2 MB | `lm-skoter.img`, 912,384 bytes |
| **Total build** | **1,296.31 s (21 min 36 s)** | **4,574.9 MB** | **Two maps** |

The build met the 45-minute and 8 GB targets and both outputs are below the
3.5 GB build limit for FAT32. The largest stage RSS is a process peak reported
by the pipeline. Both images passed structural verification. The base map
decoded at seven levels. The overlay has all four snowmobile statuses, with
5,920 line segments and 748 type-1836 markers at level 0. See the
[Garmin ID check](../garmin-ids.md#v01-candidate-check) for the tested device files.

A second map for Gotland (`--county 09 --products topo50`, ten jobs) took
18.62 seconds, within the five-minute county target. It used the Topografi 50
county boundary with the SCB index for name and code lookup.

## Stage cache around Storuman (issue #25)

Built the base map for Storuman using Topografi 50, 100 and 250, with four
jobs and the default splitter configuration. The first build used a fresh
stage cache, including the initial GeoPackage fingerprints.

| Build | Wall time | Stages executed |
|---|---:|---|
| Cold | 108.79 s | Convert, overview extract, split and compile |
| Identical rebuild | 0.01 s | Reused all cached stages |
| Changed the water colour | 10.55 s | Compile only |


## Decoded object budgets

The default base map has seven detail levels. The counts below are from the
50 × 50 km Tärnaby extract after the lake, forest and wetland overview changes, using
one Garmin tile. Counts come from the compiled map and include pieces split
by the Garmin compiler and the tile background polygon.

| Level | Resolution | Points | Lines | Polygons |
|---|---:|---:|---:|---:|
| 0 | 24 | 6,148 | 23,005 | 21,207 |
| 1 | 23 | 6,148 | 22,199 | 20,940 |
| 2 | 22 | 1,210 | 11,611 | 19,902 |
| 3 | 21 | 1,042 | 7,621 | 17,586 |
| 4 | 20 | 201 | 1,726 | 11,943 |
| 5 | 18 | 4 | 26 | 2,148 |
| 6 | 16 | 2 | 0 | 1 |

At level 4, firm wetlands, open ground and mountain birch forest are the
largest polygon classes by count (3,814, 3,744 and 2,313 respectively).

Each upper limit is the measured count plus 15% (rounded up), with room for at
least two extra objects in nonempty categories. Empty categories have a limit
of zero. The same rule sets the budgets for the three fixture builds checked
in CI. Update an individual limit when an intentional style change warrants
it and report the before and after counts.

```bash
uv run lm-garmin build --bbox 490000,7265000,540000,7315000 --products topo50 \
  --max-nodes 4000000 --dev --out dist/tarnaby-overview
uv run lm-garmin verify dist/tarnaby-overview/lm-dev-topo50.img --level-counts \
  --expect docs/benchmarks/tarnaby-overview.json
uv run pytest -q -m local_data -k tarnaby_overview_budget
```

Set `LM_GARMIN_OVERVIEW_IMG` to check a build at another path. Use the same
extent, delivery and tile layout when comparing the counts. The local test
skips if the map has yet to be built.

## Firm wetland overview around Tärnaby (issue #15)

At resolution 20, firm wetlands (`2651`) must cover at least 4,000 Garmin
square units, roughly 0.94 ha at Tärnaby's latitude. Smaller firm wetlands
remain eligible at resolution 21 and finer. The cutoff is based on the
polygon's size on the map and varies in hectares with latitude.
[mkgmap style manual](https://www.mkgmap.org.uk/doc/pdf/style-manual.pdf)

| Resolution-20 check | Before | After |
|---|---:|---:|
| Firm wetland polygons (`0x51`) | 4,385 | 3,814 |
| Firm wetland area inside the extract | 195.68 km² | 192.54 km² |
| Wet wetland polygons (`0x10f04`) | 37 | 37 |
| Total decoded polygons | 12,521 | 11,943 |

After clipping both outputs to the benchmark extent, 98.39% of the previous
firm wetland area still overlaps the new output. Object counts at the other
detail levels match. The integration test checks that a small firm wetland
appears at resolution 21 and finer and that a larger firm wetland and a wet
wetland still appear at resolution 20.

## Forest overview around Tärnaby (issue #15)

Reused the 50 × 50 km lake benchmark extent with the same single Garmin tile
in both builds (`--max-nodes 4000000`). The converter joined 62 coniferous and
mixed-forest source polygons into 16 groups across the Topografi 50 grid.

| Resolution-20 check | Source fragments | Joined forest |
|---|---:|---:|
| Decoded forest polygons (`0x50`) | 359 | 325 |
| Forest area overlap with source (IoU) | 95.74% | 95.84% |
| Decoded forest overlapping source water | 1.58 km² | 1.48 km² |
| Decoded forest overlapping source open ground | 2.44 km² | 2.35 km² |

The integration test checks that the join is limited to resolution 20 and
that a lake and a clearing remain open in the compiled map. At 2 km on the
Montana 700, the shared view around Forsbäck and Gakkervattnet looked similar
before and after. After aligning the panned screenshots, the remaining visible
differences were small changes at forest edges. Water and open patches remained
visible, with no obvious new straight breaks in the shared view.

The joins are bounded by a 50 km processing grid. In a nationwide dry run of the dissolve
step, 9,735 groups were produced from 46,275 fragments in about two minutes.
Their WKB occupied about 517 MB. The converter stages those polygons on disk
while it writes the source data, keeping their output order and avoiding
holding the entire overview in memory. Whole-country Garmin build performance
still needs a separate measurement.

## Lake overview around Tärnaby (issue #15)

Compared two builds of the same 50 × 50 km extent in SWEREF 99 TM
(`490000,7265000,540000,7315000`). The converter joined 89 lake identifiers
from the Topografi 50 source. The table counts decoded lake polygons (Garmin type
`0x3c`), which can be split again at Garmin tile boundaries.

| mkgmap resolution | Source fragments | Merged lake overview |
|---|---:|---:|
| 24 | 2,990 | 2,990 |
| 21 | 1,906 | 1,906 |
| 20 | 976 | 948 |
| 18 | 248 | 248 |

At resolution 20, the overlap with the source lake areas (intersection over
union) went from 91.99% to 92.06% after clipping the decoded geometry and the
source to the benchmark extent. The decoded lake geometry at resolutions
24, 23, 22, 21 and 18 matched exactly. An exploratory build that also showed
the union at resolution 18 increased the lake-area difference against the
source in the Tärnaby comparison window from 10.26 to 10.81 km². The default
style therefore uses the union at resolution 20.

On the Montana 700, the before and after screenshots at 2 km showed similar
lake outlines around Laxnäs and Stor-Laisan. The frames were panned slightly
between captures. After alignment, the differences in lake fill were small
and no obvious new gaps or lost islands appeared in the shared view. The
synthetic seam test covers seam removal directly; this device comparison
checks the appearance of the actual lake data.

The nationwide *lake-merge step alone* processed 10,822 lake identifiers in
5.7 s with a 532 MB process peak. The nationwide Garmin build remains a
separate benchmark.

## 2026-11-18 – S0 unpack + S1 convert, all of Sweden (branch `m1/unpack-region-convert`)

| Step | Wall | CPU | Peak RSS | Output |
|---|---:|---:|---:|---|
| `lm-garmin unpack` (13 zips from NAS) | 75 s | 17 s | 115 MB | 14 GB GeoPackage, 70–75 MB/s |
| `lm-garmin convert --region sweden` (13 themes in parallel) | **490 s** | 1 175 s | 540 MB | 2.3 GB PBF, 18.6 M features, 579 M nodes |

Per theme (from [`2026-11-18-convert-sweden.json`](2026-11-18-convert-sweden.json)):
`hojd` 489 s (302 M nodes) and `mark` 440 s (224 M nodes) run alone for most of the time;
everything else is done within 100 s. Wall time is therefore set by the two largest themes,
not by the machine.

Next steps (issue #27): split `hojd` and `mark` into spatial chunks (by R-tree, e.g. 50 km
cells) so all cores are used – expected ≈ 2–3 min; profile the per-node Python loop
(~1.6 µs/node) if needed.

For comparison, the naive XML spike needed 68 s for one 50×50 km tile; the converter does
the same Stockholm tile in 6.7 s (24 MB PBF instead of 509 MB XML).

## 2026-11-18 – full build of Sweden, `lm-garmin build --region sweden` (branch `m1/build-style-verify`)

First style (generated from `styles/*/mapping.csv`), mkgmap `-Xmx4g`, 10 jobs.
Report: [`2026-11-18-build-sweden.json`](2026-11-18-build-sweden.json).

| Step | Wall | Peak RSS | Result |
|---|---:|---:|---|
| convert (S1) | 458 s | 527 MB | 18.6 M features |
| split, base map | 229 s | 2.7 GB | 380 tiles |
| compile, base map (mkgmap + index + gmapsupp) | 384 s | 4.5 GB | `lm-topo50.img` **2.02 GB** |
| extract + split + compile, overlay | 3 s | 0.3 GB | `lm-skoter.img` 0.9 MB, 5 334 lines, 748 points |
| **Total** | **1 076 s (17.9 min)** | 4.5 GB | |

`lm-garmin verify` decodes the 2 GB base map in 419 s (530 MB RSS): 380 tiles, 7 levels,
141 Garmin types, 14.2 M objects on level 0, 231 643 distinct labels. All 748 points of
type 1836 are in the overlay.

Against the plan's targets (PLAN §8): full Sweden ≤ 45 min ✔ (17.9 min), peak memory ≤ 8 GB ✔,
`.img` < 4 GB ✔ – but 2.0 GB is larger than the 0.5–1.5 GB estimate; the overview levels
(issue #15) should bring it down. Largest remaining costs: the two biggest themes in
convert (#27) and splitter on 579 M nodes.
