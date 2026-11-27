#!/usr/bin/env bash
# Bake the whole library, one Blender process per asset.
#
# Some scans are enormous (the fir tree is 465 MB / 8M triangles) and importing
# several in a row exhausts memory on a small box. A fresh process per asset
# keeps peak RSS flat at the cost of a little startup time.
#
# Usage: bash tools/bake_all.sh [--force]
set -uo pipefail
cd "$(dirname "$0")/.."
source tools/env.sh

FORCE="${1:-}"
mapfile -t KEYS < <(python3 -c "
import sys; sys.path.insert(0,'tools')
from catalog import MODELS
print('\n'.join(MODELS))
")

ok=0; fail=0; skip=0
for key in "${KEYS[@]}"; do
  if [ -z "$FORCE" ] && [ -f "assets/lib/${key}.glb" ]; then
    skip=$((skip+1)); continue
  fi
  out=$(timeout 600 blender -b -P tools/build_library.py -- --only "$key" ${FORCE:+--force} 2>&1 \
        | grep -E "tris|^  --" | head -2)
  if [ -f "assets/lib/${key}.glb" ]; then
    ok=$((ok+1)); echo "  $out"
  else
    fail=$((fail+1)); echo "  !! ${key} failed"
  fi
done
echo "baked ${ok}  skipped ${skip}  failed ${fail}"
echo "library: $(ls assets/lib/*.glb 2>/dev/null | wc -l) files, $(du -sh assets/lib 2>/dev/null | cut -f1)"
