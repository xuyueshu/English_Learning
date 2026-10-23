#!/usr/bin/env python3
"""Fill any empty Chinese translations in data/*.json.

Network blips or rate-limit challenges can leave individual paragraphs
without a translation. This scans every article, fetches the missing ones
with generous retries, updates the shared cache, and writes each article
atomically only when all of its paragraphs are translated. Re-run until it
reports zero missing paragraphs.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site as b  # noqa: E402

MAX_ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def articles_with_gaps():
    result = []
    for path in sorted(b.DATA_DIR.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        missing = [index for index, zh in enumerate(article["zh"]) if not zh.strip()]
        if missing:
            result.append((path, article, missing))
    return result


def translate_with_backoff(text: str) -> str:
    for attempt in range(6):
        translated = b.translate_paragraph(text)
        if translated.strip():
            digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
            (b.CACHE_DIR / f"{digest}.txt").write_text(translated, encoding="utf-8")
            return translated
        time.sleep(5 + attempt * 5)
    return ""


def main():
    for round_number in range(1, MAX_ROUNDS + 1):
        pending = articles_with_gaps()
        if not pending:
            print("all translations present")
            return 0

        print(f"round {round_number}: {len(pending)} articles with gaps", flush=True)
        for path, article, missing in pending:
            print(f"{article['id']}: {len(missing)} missing", flush=True)
            completed = True
            for index in missing:
                translated = translate_with_backoff(article["en"][index])
                if not translated:
                    completed = False
                    print(f"  paragraph {index} still failing", flush=True)
                    break
                article["zh"][index] = translated
                print(f"  paragraph {index} translated", flush=True)
                time.sleep(0.8)
            if completed:
                b.atomic_write_text(
                    path,
                    json.dumps(article, ensure_ascii=False, indent=2),
                )

    remaining = sum(len(missing) for _, _, missing in articles_with_gaps())
    print(f"finished with {remaining} paragraphs still missing")
    return 1 if remaining else 0


if __name__ == "__main__":
    sys.exit(main())
