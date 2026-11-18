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
