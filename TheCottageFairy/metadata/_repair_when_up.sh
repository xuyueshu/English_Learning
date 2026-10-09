#!/bin/bash
# Wait for the Google translate endpoint to recover, then run one repair pass.
# Loops until repair reports "still empty: 0". Probing first avoids hammering
# the API while it is rate-limiting us.
ROOT="/Users/youzhiqiang/Downloads/草稿/TheCottageFairy"
cd "$ROOT" || exit 1

PROBE="https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=good%20morning"

while true; do
  response=$(curl -s --max-time 12 "$PROBE")
  if [ -z "$response" ]; then
    echo "[$(date +%H:%M:%S)] endpoint blocked, sleeping 90s..."
    sleep 90
    continue
  fi

  echo "[$(date +%H:%M:%S)] endpoint up, running repair pass..."
  python3 -u "$ROOT/repair_translations.py"
  result=$(python3 - <<'PY'
import json, glob
empty = 0
for filename in glob.glob("data/*.json"):
    with open(filename, encoding="utf-8") as handle:
        article = json.load(handle)
    empty += sum(1 for paragraph in article["zh"] if not paragraph.strip())
print(empty)
PY
)
  echo "[$(date +%H:%M:%S)] empty paragraphs remaining: $result"
  if [ "$result" = "0" ]; then
    echo "all translations filled"
    python3 "$ROOT/make_manifest.py"
    break
  fi
  sleep 3
done
