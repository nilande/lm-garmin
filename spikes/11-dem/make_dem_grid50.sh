#!/usr/bin/env bash
# SPIKE (#90) – a DEM for Storuman from Lantmäteriet's Markhöjdmodell Nedladdning, grid 50+,
# as SRTM-style HGT tiles for mkgmap's --dem.
#
# The delivery is one zip per 100 x 100 km square (<N/100 km>_<E/100 km>.zip) holding one
# .xyz file: "x y z" in SWEREF 99 TM / RH 2000 with decimal commas. The points are not on a
# SWEREF-aligned grid (about 50 m apart, slightly rotated), so they are binned into 50 m
# cells and the few empty cells are filled from their neighbours.
#
# Usage: spikes/11-dem/make_dem_grid50.sh [GRID50_DIR]   (output in spikes/11-dem/out-grid50/)
set -euo pipefail
SRC=${1:-"/Volumes/scratch/lm-kartdata/Markhöjdmodell Nedladdning, grid 50+"}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/out-grid50
# Storuman municipality bbox (SWEREF 99 TM) + 10 km, snapped to 50 m
XMIN=466000 YMIN=7171000 XMAX=650000 YMAX=7347000
mkdir -p "$OUT/hgt" "$OUT/xyz"
rm -f "$OUT"/raw.tif "$OUT"/dem.tif "$OUT"/hgt/*.hgt

for n in 71 72 73; do
  for e in 4 5 6; do
    z="$SRC/${n}_${e}.zip"
    [ -f "$z" ] || continue
    csv="$OUT/xyz/${n}_${e}.csv"
    [ -f "$csv" ] || { echo "x,y,z"; unzip -p "$z" | tr ',' '.' | tr ' ' ','; } > "$csv"
  done
done

# One VRT over all CSV squares, read as points.
{
  echo '<OGRVRTDataSource><OGRVRTUnionLayer name="pts">'
  for csv in "$OUT"/xyz/*.csv; do
    b=$(basename "$csv" .csv)
    echo "<OGRVRTLayer name=\"$b\"><SrcDataSource>$csv</SrcDataSource>"
    echo '<GeometryType>wkbPoint</GeometryType><LayerSRS>EPSG:3006</LayerSRS>'
    echo '<GeometryField encoding="PointFromColumns" x="x" y="y" z="z"/>'
    echo '<Field name="z" type="Real"/></OGRVRTLayer>'
  done
  echo '</OGRVRTUnionLayer></OGRVRTDataSource>'
} > "$OUT/pts.vrt"

gdal_rasterize -q -a z -tr 50 50 -te $XMIN $YMIN $XMAX $YMAX -a_nodata -32768 \
  -ot Float32 -co COMPRESS=DEFLATE -l pts "$OUT/pts.vrt" "$OUT/raw.tif"
gdal_fillnodata -q -md 3 -co COMPRESS=DEFLATE "$OUT/raw.tif" "$OUT/dem.tif"

h=$(python3 -c "print(0.5/3600)")
for lat in 64 65 66; do
  for lon in 13 14 15 16 17 18; do
    name=$(printf "N%02dE%03d" $lat $lon)
    gdalwarp -q -s_srs EPSG:3006 -t_srs EPSG:4326 -r bilinear -ot Int16 \
      -srcnodata -32768 -dstnodata -32768 \
      -te $(python3 -c "print($lon-$h, $lat-$h, $lon+1+$h, $lat+1+$h)") -ts 3601 3601 \
      "$OUT/dem.tif" "$OUT/hgt/$name.tif"
    if ! gdalinfo -stats "$OUT/hgt/$name.tif" 2>/dev/null | grep -q "STATISTICS_VALID_PERCENT=[1-9]"; then
      rm -f "$OUT/hgt/$name.tif" "$OUT/hgt/$name.tif.aux.xml"
      continue
    fi
    gdal_translate -q -of SRTMHGT "$OUT/hgt/$name.tif" "$OUT/hgt/$name.hgt"
    rm -f "$OUT/hgt/$name.tif" "$OUT/hgt/$name.tif.aux.xml" "$OUT/hgt/$name.hgt.aux.xml"
  done
done
ls -l "$OUT/hgt"
