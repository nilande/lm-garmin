# lm-garmin

Build a Garmin map (`.img`) from Lantmäteriet's open topographic data
**Topografi 50 Nedladdning, vektor**, styled to resemble Lantmäteriet's printed
**Karta 1:50 000**. Primary target device: **Garmin Montana 700**.

> **Status: planning done, implementation starting.** The command line tool is a
> skeleton; see [docs/PLAN.md](docs/PLAN.md) and the
> [milestones](https://github.com/nilande/lm-garmin/milestones). Experiments that informed
> the plan are in [`spikes/`](spikes) and [docs/spikes.md](docs/spikes.md).

Map data © Lantmäteriet (CC0). This repository contains **no map data** except small test
cut-outs in [`tests/data`](tests/data/PROVENANCE.md).

## What it will do

- Convert all 13 themes of Topografi 50 (GeoPackage, SWEREF 99 TM) to a routable-ready
  OSM intermediate, then compile it with [mkgmap](https://www.mkgmap.org.uk/) and a custom
  style and TYP file into `gmapsupp.img`.
- Build all of Sweden or just a region (bounding box, county, municipality).
- Build Lantmäteriet's snowmobile information (winter trails with *skoterkörning tillåten*
  Ja / Påbjuden / Nej / Ingen information, mandatory snowmobile routes) as a **separate,
  transparent overlay** that can be switched on and off on the device.
- Make place names searchable on the device.
- Verify the built map by decoding it again (snowmobile completeness, coverage metrics,
  rendering for visual comparison with Karta 1:50 000).

## Requirements

- Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/)
- Java ≥ 17 (for mkgmap and splitter)
- GDAL command line tools – only for `scripts/make_fixtures.py`
- ~20 GB free local disk for the unpacked data cache (all of Sweden)

On macOS:

```bash
brew install uv openjdk gdal
```

## Install (development)

```bash
git clone https://github.com/nilande/lm-garmin.git
cd lm-garmin
uv sync
uv run lm-garmin tools fetch      # downloads pinned mkgmap and splitter, verifies SHA-256
uv run pytest
```

## Get the data from Geotorget

1. Create a free account at [Geotorget](https://geotorget.lantmateriet.se/).
2. Order **Topografi 50 Nedladdning, vektor** (*Geodataprodukter → Topografi 50
   Nedladdning, vektor → Beställning*), area *Sverige* (or a county), format GeoPackage.
   The product is free (CC0).
3. Download the delivery. You get one zip per theme (`hojd_sverige.zip`, `mark_sverige.zip`, …)
   and `uttag.json` — about 5.4 GB zipped, 15.3 GB unpacked for all of Sweden.
4. Optional, for visual comparison: order **Karta 1:50 000 Nedladdning, raster** (GeoTIFF)
   for the same area.

Keep the delivery anywhere; paths may contain spaces and colons
(e.g. `LM2026:173692 - Topografi 50 Nedladdning, vektor`).

## Build a map *(planned – milestone M1)*

```bash
uv run lm-garmin unpack "/path/to/LM2026:173692 - Topografi 50 Nedladdning, vektor"
uv run lm-garmin build --region sweden --out dist/
uv run lm-garmin build --bbox 500000,7250000,550000,7310000 --out dist/   # SWEREF 99 TM
```

Output: `dist/gmapsupp.img` (base map) and `dist/gmapsupp-skoter.img` (snowmobile overlay).

## Install on the Montana 700

1. Connect the device with USB (it appears as a drive), or put its microSD card in a reader.
2. Copy the `.img` files to the `Garmin/` folder (internal storage or SD card). Give each
   file a unique name, e.g. `lm-topo50.img` and `lm-skoter.img`. Files must be < 4 GB (FAT32).
3. Eject, restart the device, then *Map setup → Map information* (*Kartinställningar →
   Kartinformation*) to enable/disable the base map and the snowmobile overlay. Disable other
   maps covering the same area if they hide this one.

## Licence and attribution

Code, styles and TYP sources: [MIT](LICENSE). Map data: Lantmäteriet, CC0 – attribution is
not required, but maps built with this tool carry "© Lantmäteriet" and we ask you to keep it.
mkgmap and splitter (GPL-2.0) are downloaded at build time and run as separate programs.

---

## Sammanfattning på svenska

`lm-garmin` gör om Lantmäteriets öppna **Topografi 50** till en Garmin-karta (`.img`) för
i första hand **Garmin Montana 700**, med ett utseende som liknar **Karta 1:50 000**.
Skoterlederna i Lantmäteriets data (vinterleder med uppgift om skoterkörning är tillåten,
påbjuden eller förbjuden) byggs som ett eget genomskinligt lager som kan slås av och på
i enheten. Ortnamn blir sökbara.

Data hämtas gratis från Geotorget (se ovan). Repot innehåller ingen kartdata utöver små
testutsnitt. Projektet är i början: planen finns i [docs/PLAN.md](docs/PLAN.md) och arbetet
följs i GitHub Issues. Koden är MIT-licensierad; data © Lantmäteriet (CC0).
