#!/usr/bin/env python3
"""Build bilingual reading data from raw VTT files.

- Reconstructs clean English from YouTube rolling captions.
- Groups captions into readable paragraphs.
- Translates each paragraph to Chinese via the public gtx endpoint.
- Skips videos whose data file already exists, so it can be resumed in batches.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path


def atomic_write_text(path: Path, content: str):
    # A unique temp name per process avoids two repair processes clobbering
    # each other's temporary file. os.replace is atomic on the same filesystem,
    # so a process killed while writing can never leave a half-written file.
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "source" / "raw"
DATA_DIR = ROOT / "data"
TEXTS_DIR = ROOT / "source" / "texts"
CACHE_DIR = ROOT / ".zhcache"
VIDEO_LIST = ROOT / "source" / "metadata" / "_video_list.txt"

TAG = re.compile(r"<[^>]+>")
TIMING_LINE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3} --> ")
WORDS = re.compile(r"[A-Za-z']+")


def to_seconds(stamp: str) -> float:
    hours, minutes, seconds, millis = map(
        int, re.match(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})", stamp).groups()
    )
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def parse_vtt(path: Path):
    cues = []
    for block in re.split(r"\n\n+", path.read_text(encoding="utf-8")):
        lines = block.splitlines()
        timing = next((line for line in lines if "-->" in line), None)
        if not timing:
            continue
        timestamp = to_seconds(timing.split(" --> ")[0])
        text_lines = [
            TAG.sub("", line).strip()
            for line in lines
            if not TIMING_LINE.match(line)
        ]
        text = re.sub(r"\s+", " ", " ".join(text_lines)).strip()
        if text:
            cues.append((timestamp, text))
    return cues


def suffix_overlap_length(previous: str, current: str) -> int:
    maximum = min(len(previous), len(current))
    for length in range(maximum, 0, -1):
        if previous.endswith(current[:length]):
            return length
    return 0


def reconstruct_timed_words(cues):
    pieces = []
    accumulated = ""
    for timestamp, text in cues:
        overlap = suffix_overlap_length(accumulated, text)
        addition = text[overlap:].strip()
        if addition:
            pieces.append((timestamp, addition))
        accumulated = (accumulated + " " + addition).strip()
    return pieces


def is_sound_marker(text: str) -> bool:
    cleaned = text.replace("[", "").replace("]", "").strip()
    return bool(cleaned) and not WORDS.search(cleaned)


SOUND_TAG = re.compile(r"\[(?:Music|Laughter|Applause|Song|Singing)\]", re.IGNORECASE)


def clean_sound_tags(text: str) -> str:
    text = SOUND_TAG.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_paragraphs(timed_pieces):
    paragraphs = []
    buffer = ""
    last_start = None
    marker_times = []

    for timestamp, piece in timed_pieces:
        if is_sound_marker(piece):
            marker_times.append(piece)
            continue
        if last_start is None:
            last_start = timestamp
        buffer = (buffer + " " + piece).strip()
        if timestamp - last_start >= 45:
            cleaned = clean_sound_tags(buffer)
            if cleaned:
                paragraphs.append(cleaned)
            buffer = ""
            last_start = timestamp

    if buffer:
        cleaned = clean_sound_tags(buffer)
        if cleaned:
            paragraphs.append(cleaned)
    return paragraphs


def translate_paragraph(text: str) -> str:
    query = urllib.parse.quote(text)
    url = (
        "https://translate.googleapis.com/translate_a/single"
        "?client=gtx&sl=en&tl=zh-CN&dt=t&q=" + query
    )
    for attempt in range(5):
        try:
            output = subprocess.run(
                ["curl", "-s", url, "--max-time", "25"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            payload = json.loads(output)
            return "".join(part[0] for part in payload[0] if part[0])
        except Exception:
            time.sleep(2 + attempt * 2)
    return ""


def translate_cached(text: str) -> str:
    # Per-paragraph disk cache lets an article resume mid-way even when the
    # process is killed before the article's data file is written.
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    cache_path = CACHE_DIR / f"{digest}.txt"
    if cache_path.exists():
        cached = cache_path.read_text(encoding="utf-8")
        if cached.strip():
            return cached
    translated = translate_paragraph(text)
    if translated.strip():
        cache_path.write_text(translated, encoding="utf-8")
    return translated


def load_title_map():
    titles = {}
    if VIDEO_LIST.exists():
        for line in VIDEO_LIST.read_text(encoding="utf-8").splitlines():
            if " | " in line:
                video_id, title = line.split(" | ", 1)
                titles[video_id.strip()] = title.strip()
    return titles


def main():
    batch_limit = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    DATA_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
    title_map = load_title_map()

    vtt_files = sorted(RAW_DIR.glob("*.vtt"))
    processed = 0

    for vtt_path in vtt_files:
        if processed >= batch_limit:
            break
        match = re.search(r"\[([A-Za-z0-9_-]{11})\]\.en\.vtt$", vtt_path.name)
        if not match:
            continue
        video_id = match.group(1)
        target = DATA_DIR / f"{video_id}.json"
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
        timed_pieces = reconstruct_timed_words(cues)
        english_paragraphs = build_paragraphs(timed_pieces)
        if not english_paragraphs:
            continue

        chinese_paragraphs = []
        for paragraph in english_paragraphs:
            chinese_paragraphs.append(translate_cached(paragraph))
            time.sleep(0.6)

        atomic_write_text(
            target,
            json.dumps(
                {
                    "id": video_id,
                    "title": title,
                    "date": date,
                    "en": english_paragraphs,
                    "zh": chinese_paragraphs,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

        text_target = TEXTS_DIR / f"{video_id}.txt"
        atomic_write_text(
            text_target,
            f"{title}\n{date}\n\n"
            + "\n\n".join(english_paragraphs)
            + "\n",
        )

        processed += 1
        print(f"[{processed}] {video_id} {title[:50]}")

    print(f"batch done: {processed}")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_manifest.py")],
        check=False,
    )


if __name__ == "__main__":
    main()
