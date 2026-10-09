#!/bin/bash
# Repeatedly run build_site.py until the data directory reaches the target count.
# build_site.py skips articles whose data JSON already exists, so this is safe to restart.
TARGET="$1"
ROOT="/Users/youzhiqiang/Downloads/草稿/TheCottageFairy"
cd "$ROOT" || exit 1

while true; do
  count=$(ls data/*.json 2>/dev/null | wc -l | tr -d ' ')
  if [ "$count" -ge "$TARGET" ]; then
    echo "reached target: $count >= $TARGET"
    break
  fi
  echo "[$(date +%H:%M:%S)] have $count, target $TARGET, starting build..."
  python3 -u "$ROOT/build_site.py" "$TARGET"
  echo "[$(date +%H:%M:%S)] build process exited with $?"
  sleep 2
done
