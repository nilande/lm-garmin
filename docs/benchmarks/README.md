# Benchmarks

Reference machine: Apple M5 (10 cores), 16 GB RAM, internal SSD; data on an SMB share (NAS).
Delivery `LM2026:173692` (data 2026-10-16).

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
