#!/usr/bin/env python3
"""Quickly export clean English txt files from raw VTT captions.

No network access; skips files already exported.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_site import (  # noqa: E402
    RAW_DIR,
    TEXTS_DIR,
    build_paragraphs,
    load_title_map,
    parse_vtt,
    reconstruct_timed_words,
)
import re  # noqa: E402
from pathlib import Path  # noqa: E402


def main():
    TEXTS_DIR.mkdir(exist_ok=True)
    title_map = load_title_map()
    exported = 0

    for vtt_path in sorted(RAW_DIR.glob("*.vtt")):
        match = re.search(r"\[([A-Za-z0-9_-]{11})\]\.en\.vtt$", vtt_path.name)
        if not match:
            continue
        video_id = match.group(1)
        target = TEXTS_DIR / f"{video_id}.txt"
        if target.exists():
            continue

        date_match = re.match(r"(\d{4})(\d{2})(\d{2})", vtt_path.name)
        date = (
            f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            if date_match
            else ""
        )
        title = title_map.get(video_id, vtt_path.name.split(" [")[0])

        cues = parse_vtt(vtt_path)
        paragraphs = build_paragraphs(reconstruct_timed_words(cues))
        if not paragraphs:
            continue

        target.write_text(
            f"{title}\n{date}\n\n" + "\n\n".join(paragraphs) + "\n",
            encoding="utf-8",
        )
        exported += 1

    print(f"exported: {exported}")


if __name__ == "__main__":
    main()
