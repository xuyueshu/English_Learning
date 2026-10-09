#!/bin/bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1

while true; do
  echo "[$(date +%H:%M:%S)] repair pass starting..."
  python3 -u "$ROOT/scripts/repair_translations.py"
  last=$(grep "still empty" "$ROOT/logs/_repair_cum.log" 2>/dev/null | tail -n 1)
  echo "last result: $last"
  case "$last" in
    *"still empty: 0") echo "all translations filled"; break;;
  esac
  sleep 2
done
