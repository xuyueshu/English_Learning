#!/usr/bin/env python3
"""One-time cleanup of YouTube ASR "foreign" markers in already-built data.

Older builds kept the literal "foreign" token that YouTube inserts for
inaudible or musical sections. This script:

- removes the marker from every English paragraph in data/*.json,
- drops paragraphs (and their translations) that consist only of markers,
- re-translates every changed paragraph,
- rewrites the matching source/texts/*.txt exports,
- cleans marker-only paragraphs from text exports without a data file,
- regenerates manifest.json at the end.

Writes are atomic and every article is saved immediately, so an interrupted
run can safely be restarted: cleaned paragraphs no longer contain the marker.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site as b  # noqa: E402


def clean_text(text: str) -> str:
    return " ".join(b.ASR_FOREIGN.sub(" ", text).split())


def write_text_export(article: dict):
    text_path = b.TEXTS_DIR / f"{article['id']}.txt"
    text_path.write_text(
        f"{article['title']}\n{article['date']}\n\n"
        + "\n\n".join(article["en"])
        + "\n",
        encoding="utf-8",
    )


def clean_data_files():
    articles_changed = 0
    paragraphs_retranslated = 0
    paragraphs_dropped = 0

    for data_path in sorted(b.DATA_DIR.glob("*.json")):
        article = json.loads(data_path.read_text(encoding="utf-8"))
        cleaned_pairs = []
        changed = False

        for english, chinese in zip(article["en"], article["zh"]):
            cleaned = clean_text(english)
            if not cleaned:
                changed = True
                paragraphs_dropped += 1
                continue
            if cleaned != english:
                changed = True
                chinese = b.translate_cached(cleaned)
                paragraphs_retranslated += 1
                time.sleep(0.6)
            cleaned_pairs.append((cleaned, chinese))

        if not changed:
            continue

        article["en"] = [pair[0] for pair in cleaned_pairs]
        article["zh"] = [pair[1] for pair in cleaned_pairs]
        b.atomic_write_text(
            data_path,
            json.dumps(article, ensure_ascii=False, indent=2),
        )
        write_text_export(article)
        articles_changed += 1
        print(f"{article['id']} cleaned", flush=True)

    print(
        f"data: {articles_changed} articles changed, "
        f"{paragraphs_retranslated} retranslated, "
        f"{paragraphs_dropped} marker-only paragraphs dropped"
    )


def clean_orphan_texts():
    data_ids = {path.stem for path in b.DATA_DIR.glob("*.json")}
    cleaned_files = 0

    for text_path in sorted(b.TEXTS_DIR.glob("*.txt")):
        if text_path.stem in data_ids:
            continue
        lines = text_path.read_text(encoding="utf-8").splitlines()
        if len(lines) < 3:
            continue
        header = lines[:2]
        body = "\n".join(lines[2:])
        blocks = [
            clean_text(block)
            for block in body.split("\n\n")
        ]
        blocks = [block for block in blocks if block]
        if not any(b.ASR_FOREIGN.search(line) for line in lines[2:]):
            continue
        text_path.write_text(
            "\n".join(header) + "\n\n" + "\n\n".join(blocks) + "\n",
            encoding="utf-8",
        )
        cleaned_files += 1

    print(f"orphan text exports cleaned: {cleaned_files}")


def main():
    b.CACHE_DIR.mkdir(exist_ok=True)
    b.TEXTS_DIR.mkdir(exist_ok=True)
    clean_data_files()
    clean_orphan_texts()
    b.subprocess.run(
        [sys.executable, str(b.ROOT / "scripts" / "make_manifest.py")],
        check=False,
    )


if __name__ == "__main__":
    main()
