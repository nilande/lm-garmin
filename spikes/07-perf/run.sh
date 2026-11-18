#!/bin/bash
# SPIKE – time the naive pipeline on one 50x50 km raster tile.
set -euo pipefail
cd "$(dirname "$0")"
J=/opt/homebrew/opt/openjdk/bin/java; T=../../tools
name=$1; shift; bbox=("$@")
[ -f $name/clip.gpkg ] && mv $name/clip.gpkg $name.clip.gpkg; rm -rf $name; mkdir -p $name
t() { local s=$(date +%s); /usr/bin/time -l "$@" 2> $name/.time >/dev/null || { cat $name/.time; exit 1; }; echo "$(( $(date +%s)-s ))s rss=$(awk '/maximum resident/{printf "%.0fMB",$1/1e6}' $name/.time)"; }
[ -f $name.clip.gpkg ] && { mkdir -p $name; mv $name.clip.gpkg $name/clip.gpkg; } || echo "clip:     $(t ../02-clip/${CLIPPER:-clip.sh} ~/.cache/lm-garmin/gpkg $name/clip.gpkg "${bbox[@]}")"
ls -la $name/clip.gpkg | awk '{printf "  clip.gpkg %.0f MB\n",$5/1e6}'
echo "gpkg2osm: $(t uv run -q --project ../03-mkgmap ../03-mkgmap/gpkg2osm.py $name/clip.gpkg $name/all.osm)"
ls -la $name/all.osm | awk '{printf "  all.osm %.0f MB\n",$5/1e6}'
echo "splitter: $(t $J -Xmx4g -jar $T/splitter-r654/splitter.jar --output-dir=$name/split --mapid=57400001 --max-nodes=1600000 --max-threads=10 $name/all.osm)"
ls $name/split/*.osm.pbf | wc -l | awk '{print "  tiles:",$1}'
echo "mkgmap:   $(t $J -Xmx6g -jar $T/mkgmap-r4924/mkgmap.jar --output-dir=$name/img --style-file=../03-mkgmap/style/lm --family-id=5740 --product-id=1 --unicode --lower-case --index --gmapsupp --max-jobs=10 -c $name/split/template.args ../03-mkgmap/typ/lm-uni.txt)"
ls -la $name/img/gmapsupp.img | awk '{printf "  gmapsupp.img %.1f MB\n",$5/1e6}'
