#!/bin/bash
# Resumable subtitle downloader. Re-running it skips videos whose .vtt exists.
set -u
cd "$(dirname "$0")/.." || exit 1

FOLDER="TheCottageFairy"
PROXY="http://127.0.0.1:1082"

while IFS= read -r video_id; do
  if ls "$FOLDER"/*"[${video_id}].en.vtt" >/dev/null 2>&1; then
    continue
  fi
  yt-dlp \
    --proxy "$PROXY" \
    --write-auto-sub \
    --sub-lang en \
    --skip-download \
    --ignore-errors \
    --no-playlist \
    --retries 5 \
    -o "${FOLDER}/%(upload_date)s - %(title)s [%(id)s].%(ext)s" \
    "https://www.youtube.com/watch?v=${video_id}"
done < "$FOLDER/_video_ids.txt"
