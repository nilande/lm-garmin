#!/bin/bash
# SPIKE – clip all layers of all theme GeoPackages to a bbox (EPSG:3006).
# Usage: clip.sh <gpkg-dir> <out.gpkg> xmin ymin xmax ymax
set -euo pipefail
src="$1"; out="$2"; shift 2
rm -f "$out"
for g in "$src"/*.gpkg; do
  case "$(basename "$g")" in ._*) continue;; esac
  for l in $(ogrinfo -q -ro "$g" | sed -nE 's/^[0-9]+: ([a-z_]+).*/\1/p'); do
    ogr2ogr -f GPKG -update -append "$out" "$g" "$l" -nln "$l" \
      -spat "$@" -nlt PROMOTE_TO_MULTI -skipfailures 2>/dev/null || true
  done
done
