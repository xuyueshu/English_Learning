#!/usr/bin/env python3
"""Re-segment built articles with the sentence-aware paragraph splitter.

Raw VTT captions are rebuilt with build_site.build_paragraphs, which breaks
paragraphs at sentence boundaries (commas after a short grace period, with a
safety cut for unpunctuated captions). Existing Chinese translations are
reused when an old paragraph matches a new one exactly; every other new
paragraph is translated.

An article is left untouched when any of its new translations cannot be
fetched (e.g. Google rate limiting), so partially translated data is never
written. Re-running resumes automatically: finished articles already match
the new segmentation, and successful paragraph translations are cached.
Pass --dry-run to only report the work required.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site as b  # noqa: E402

DRY_RUN = "--dry-run" in sys.argv


def write_text_export(video_id: str, title: str, date: str, paragraphs):
    (b.TEXTS_DIR / f"{video_id}.txt").write_text(
        f"{title}\n{date}\n\n" + "\n\n".join(paragraphs) + "\n",
        encoding="utf-8",
    )


def find_vtt(video_id: str):
    suffix = f"[{video_id}].en.vtt"
    matches = [path for path in b.RAW_DIR.glob("*.vtt") if path.name.endswith(suffix)]
    return matches[0] if matches else None


def resegment_data():
    articles_changed = 0
    paragraphs_translated = 0
    paragraphs_reused = 0
    skipped = []

    for data_path in sorted(b.DATA_DIR.glob("*.json")):
        article = json.loads(data_path.read_text(encoding="utf-8"))
        vtt_path = find_vtt(article["id"])
        if vtt_path is None:
            skipped.append((article["id"], "missing raw vtt"))
            continue

        cues = b.parse_vtt(vtt_path)
        new_paragraphs = b.build_paragraphs(b.reconstruct_timed_words(cues))
        if not new_paragraphs or new_paragraphs == article["en"]:
            continue

        old_translations = dict(zip(article["en"], article["zh"]))
        new_chinese = []
        file_reused = 0
        failed = False

        for paragraph in new_paragraphs:
            cached_translation = old_translations.get(paragraph)
            if cached_translation:
                new_chinese.append(cached_translation)
                file_reused += 1
                paragraphs_reused += 1
                continue

            if DRY_RUN:
                new_chinese.append("")
                paragraphs_translated += 1
                continue

            translated = b.translate_cached(paragraph)
            if not translated:
                failed = True
                break
            new_chinese.append(translated)
            paragraphs_translated += 1
            time.sleep(0.4)

        if DRY_RUN:
            articles_changed += 1
            print(
                f"{article['id']}: {len(article['en'])} -> {len(new_paragraphs)} "
                f"(reuse {file_reused}, translate {len(new_paragraphs) - file_reused})"
            )
            continue

        if failed:
            skipped.append((article["id"], "translation unavailable"))
            print(f"SKIP {article['id']} (translation unavailable)", flush=True)
            continue

        article["en"] = new_paragraphs
        article["zh"] = new_chinese
        b.atomic_write_text(
            data_path,
            json.dumps(article, ensure_ascii=False, indent=2),
        )
        write_text_export(
            article["id"], article["title"], article["date"], new_paragraphs
        )
        articles_changed += 1
        print(f"{article['id']} resegmented", flush=True)

    print(
        f"articles changed: {articles_changed}, translations reused: "
        f"{paragraphs_reused}, translations fetched: {paragraphs_translated}, "
        f"skipped: {skipped}"
    )
    return not skipped


def rebuild_all_texts():
    title_map = b.load_title_map()
    written = 0
    for vtt_path in sorted(b.RAW_DIR.glob("*.vtt")):
        match = b.re.search(r"\[([A-Za-z0-9_-]{11})\]\.en\.vtt$", vtt_path.name)
        if not match:
            continue
        video_id = match.group(1)
        date_match = b.re.match(r"(\d{4})(\d{2})(\d{2})", vtt_path.name)
        date = (
            f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            if date_match
            else ""
        )
        title = title_map.get(video_id, vtt_path.name.split(" [")[0])
        cues = b.parse_vtt(vtt_path)
        paragraphs = b.build_paragraphs(b.reconstruct_timed_words(cues))
        if paragraphs:
            write_text_export(video_id, title, date, paragraphs)
            written += 1
    print(f"text exports written: {written}")


def main():
    b.TEXTS_DIR.mkdir(exist_ok=True)
    complete = resegment_data()
    if not DRY_RUN and complete:
        rebuild_all_texts()
        b.subprocess.run(
            [sys.executable, str(b.ROOT / "scripts" / "make_manifest.py")],
            check=False,
        )


if __name__ == "__main__":
    main()
