#!/bin/bash
# SPIKE – device test kit v2: fixtures + a tile with Sami names (ŋ), built with the M1 converter
# and the spike style (tags renamed to schema v1). Output: spikes/06-device-test/Garmin/
#
# Every map gets its own tile numbers: a Garmin device silently skips a map whose tile
# numbers are already loaded from another file.
#   latin base 5730xxxx, latin overlay 5731xxxx, unicode base 5732xxxx, unicode overlay 5733xxxx
set -euo pipefail
R=$(cd "$(dirname "$0")/../.." && pwd); K=$R/spikes/06-device-test; W=$K/build2
J=${LM_GARMIN_JAVA:-/opt/homebrew/opt/openjdk/bin/java}; T=$HOME/.cache/lm-garmin/tools
AREAS=(fjall_727_51_05 tatort_659_67_00 skoter_730_51 samiska)

rm -rf "$W" "$K/Garmin"
mkdir -p "$W/src" "$K/Garmin"
uv run --project "$R" lm-garmin tools fetch >/dev/null

# 1) convert: three fixtures + Sami-name tile from the full data
for f in fjall_727_51_05 tatort_659_67_00 skoter_730_51; do
  mkdir -p "$W/src/$f"; ln -s "$R/tests/data/$f.gpkg" "$W/src/$f/"
  uv run --project "$R" lm-garmin convert --gpkg-dir "$W/src/$f" --region sweden --out "$W/pbf/$f" >/dev/null
done
uv run --project "$R" lm-garmin convert --bbox 566000,7250000,572000,7263000 --out "$W/pbf/samiska" >/dev/null

# 2) styles: spike style with schema-v1 tag names
for s in lm skoter; do
  cp -r "$R/spikes/03-mkgmap/style/$s" "$W/style-$s"
  for f in "$W/style-$s"/*; do
    sed -i '' -e 's/lm:sk=/lm:skoterkorning_tillaten=/g' -e 's/lm:idx=yes/lm:stodkurva=Ja/g' \
      -e 's/lm:cat=/lm:textkategori=/g' -e 's/lm:size>=5/lm:textstorleksklass>=5/g' "$f"
  done
done

# split all areas with tile numbers starting at $1 into $2; prints the tile files
split_all() {
  local base=$1 out=$2 i=0 a p
  for a in "${AREAS[@]}"; do
    local inputs=()
    for p in "$W/pbf/$a"/*.osm.pbf; do [ "$(stat -f %z "$p")" -gt 200 ] && inputs+=("$p"); done
    "$J" -jar "$T/splitter-r654/splitter.jar" --output-dir="$out/$a" --mapid=$((base + i * 10)) \
      "${inputs[@]}" >/dev/null 2>&1
    ls "$out/$a"/*.osm.pbf
    i=$((i + 1))
  done
}

# 3) compile base + overlay for both encodings
for v in latin unicode; do
  if [ $v = latin ]; then enc=(--code-page=1252 --lower-case); tb=lm.txt; ts=skoter.txt; fb=5730; fs=5731
  else enc=(--unicode --lower-case); tb=lm-uni.txt; ts=skoter-uni.txt; fb=5732; fs=5733; fi
  tiles=()
  while IFS= read -r t; do tiles+=("$t"); done < <(split_all "${fb}0001" "$W/split-$v")
  "$J" -jar "$T/mkgmap-r4924/mkgmap.jar" --output-dir="$W/$v-bas" --style-file="$W/style-lm" \
    --family-id=$fb --product-id=1 --family-name="LM Topo50 test ($v)" --series-name="LM Topo50 test ($v)" \
    --description="LM Topo50 test ($v)" --copyright-message="© Lantmäteriet" "${enc[@]}" --index --gmapsupp \
    "${tiles[@]}" "$R/spikes/03-mkgmap/typ/$tb" 2>&1 | grep -iE 'severe|error' || true
  "$J" -jar "$T/mkgmap-r4924/mkgmap.jar" --output-dir="$W/$v-skoter" --style-file="$W/style-skoter" \
    --family-id=$fs --product-id=1 --family-name="LM skoterleder test ($v)" --series-name="LM skoterleder test ($v)" \
    --description="LM skoterleder test ($v)" --copyright-message="© Lantmäteriet" "${enc[@]}" \
    --transparent --draw-priority=30 --gmapsupp --mapname=${fs}0001 \
    "$W/pbf/skoter_730_51/kommunikation.osm.pbf" "$R/spikes/03-mkgmap/typ/$ts" 2>&1 | grep -iE 'severe|error' || true
  cp "$W/$v-bas/gmapsupp.img" "$K/Garmin/lmtest-$v-bas.img"
  cp "$W/$v-skoter/gmapsupp.img" "$K/Garmin/lmtest-$v-skoter.img"
done
ls -la "$K/Garmin"
