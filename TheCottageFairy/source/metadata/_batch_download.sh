#!/bin/bash
# Resumable subtitle downloader. Re-running it skips videos whose .vtt exists.
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RAW_DIR="$ROOT/source/raw"
VIDEO_IDS="$ROOT/source/metadata/_video_ids.txt"
PROXY="http://127.0.0.1:1082"

while IFS= read -r video_id; do
  if ls "$RAW_DIR"/*"[${video_id}].en.vtt" >/dev/null 2>&1; then
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
    -o "$RAW_DIR/%(upload_date)s - %(title)s [%(id)s].%(ext)s" \
    "https://www.youtube.com/watch?v=${video_id}"
done < "$VIDEO_IDS"
