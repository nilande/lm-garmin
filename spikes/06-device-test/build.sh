#!/bin/bash
# SPIKE – build the device test kit (Latin-1 vs Unicode, base + transparent overlay).
set -euo pipefail
cd "$(dirname "$0")/../03-mkgmap"
J=/opt/homebrew/opt/openjdk/bin/java; MK=../../tools/mkgmap-r4924/mkgmap.jar; K=../06-device-test
rm -rf $K/build $K/Garmin; mkdir -p $K/build $K/Garmin
for v in latin unicode; do
  if [ $v = latin ]; then enc=(--code-page=1252 --lower-case); tb=typ/lm.txt; ts=typ/skoter.txt; fb=5730; fs=5731
  else enc=(--unicode --lower-case); tb=typ/lm-uni.txt; ts=typ/skoter-uni.txt; fb=5732; fs=5733; fi
  $J -jar $MK --output-dir=$K/build/$v-base --style-file=style/lm --family-id=$fb --product-id=1 \
    --family-name="LM Topo50 test ($v)" --series-name="LM Topo50 test ($v)" --description="LM Topo50 test ($v)" \
    --copyright-message="© Lantmäteriet" "${enc[@]}" --index --gmapsupp \
    --mapname=${fb}0001 fjall_727_51_05.osm --mapname=${fb}0002 tatort_659_67_00.osm --mapname=${fb}0003 skoter_730_51.osm $tb \
    2>&1 | grep -iE 'severe|error' || true
  $J -jar $MK --output-dir=$K/build/$v-skoter --style-file=style/skoter --family-id=$fs --product-id=1 \
    --family-name="LM skoterleder test ($v)" --series-name="LM skoterleder test ($v)" --description="LM skoterleder test ($v)" \
    --copyright-message="© Lantmäteriet" "${enc[@]}" --transparent --draw-priority=30 --gmapsupp \
    --mapname=${fs}0001 skoter_730_51.overlay.osm --mapname=${fs}0002 fjall.overlay.osm $ts \
    2>&1 | grep -iE 'severe|error' || true
  cp $K/build/$v-base/gmapsupp.img $K/Garmin/lmtest-$v-bas.img
  cp $K/build/$v-skoter/gmapsupp.img $K/Garmin/lmtest-$v-skoter.img
done
ls -la $K/Garmin
