#!/usr/bin/env bash
# SPIKE (#90) – a DEM for Storuman from Topografi 50 contours, as SRTM-style HGT tiles.
#
# Stand-in until Lantmäteriet's elevation model (Markhöjdmodell, grid 50+) is ordered:
# rasterize contours and spot heights at RES m, fill the gaps between them, then cut
# 1° x 1° tiles at 1 arc-second (3601 x 3601) in WGS 84, which mkgmap's --dem reads.
#
# Usage: spikes/11-dem/make_dem.sh [RES]   (output in spikes/11-dem/out/)
set -euo pipefail
RES=${1:-25}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/out
GPKG=${LM_GARMIN_CACHE:-$HOME/.cache/lm-garmin}/gpkg/hojd_sverige.gpkg
# Storuman municipality bbox (SWEREF 99 TM) + 10 km
XMIN=466000 YMIN=7171000 XMAX=650000 YMAX=7347000
mkdir -p "$OUT/hgt"
rm -f "$OUT"/contours.gpkg "$OUT"/raw.tif "$OUT"/dem.tif "$OUT"/hgt/*.hgt

ogr2ogr -f GPKG "$OUT/contours.gpkg" "$GPKG" -spat $XMIN $YMIN $XMAX $YMAX \
  -dialect SQLite -sql "SELECT geom, CAST(hojdvarde AS REAL) AS z FROM hojdlinje" -nln c
ogr2ogr -f GPKG "$OUT/contours.gpkg" "$GPKG" -update -spat $XMIN $YMIN $XMAX $YMAX \
  -dialect SQLite -sql "SELECT geom, CAST(hojdvarde AS REAL) AS z FROM hojdpunkt" -nln p

gdal_rasterize -q -a z -tr "$RES" "$RES" -te $XMIN $YMIN $XMAX $YMAX -a_nodata -32768 \
  -ot Float32 -co COMPRESS=DEFLATE -l c "$OUT/contours.gpkg" "$OUT/raw.tif"
gdal_rasterize -q -a z -l p "$OUT/contours.gpkg" "$OUT/raw.tif"
# Inverse-distance fill between contours, then smoothing passes against terracing.
gdal_fillnodata -q -md 200 -si 2 -co COMPRESS=DEFLATE "$OUT/raw.tif" "$OUT/dem.tif"

for lat in 64 65 66; do
  for lon in 13 14 15 16 17 18; do
    name=$(printf "N%02dE%03d" $lat $lon)
    h=$(python3 -c "print(0.5/3600)")
    gdalwarp -q -s_srs EPSG:3006 -t_srs EPSG:4326 -r bilinear -ot Int16 \
      -srcnodata -32768 -dstnodata -32768 \
      -te $(python3 -c "print($lon-$h, $lat-$h, $lon+1+$h, $lat+1+$h)") -ts 3601 3601 \
      "$OUT/dem.tif" "$OUT/hgt/$name.tif"
    # keep only tiles with data
    if gdalinfo -stats "$OUT/hgt/$name.tif" 2>/dev/null | grep -q "STATISTICS_VALID_PERCENT=0$"; then
      rm "$OUT/hgt/$name.tif"
      continue
    fi
    gdal_translate -q -of SRTMHGT "$OUT/hgt/$name.tif" "$OUT/hgt/$name.hgt"
    rm -f "$OUT/hgt/$name.tif" "$OUT/hgt/$name.tif.aux.xml"
  done
done
ls -l "$OUT/hgt"
