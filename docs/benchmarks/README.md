# Benchmarks

Reference machine: Apple M5 (10 cores), 16 GB RAM, internal SSD; data on an SMB share (NAS).
Delivery `LM2026:173692` (data 2026-10-16).

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
