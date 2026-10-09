#!/usr/bin/env python3
"""Fill any empty Chinese translations inside existing data files.

Each repaired paragraph is written back immediately, so this is safe to
restart when the process is killed. Paragraph translations are served from
build_site.translate_cached, which no longer caches empty results.
"""
import json
from pathlib import Path

import build_site as b


def main():
    b.CACHE_DIR.mkdir(exist_ok=True)
    remaining = 0
    repaired = 0

    for data_path in sorted(b.DATA_DIR.glob("*.json")):
        article = json.loads(data_path.read_text(encoding="utf-8"))
        changed = False

        for index, chinese in enumerate(article.get("zh", [])):
            if chinese.strip():
                continue
            if index >= len(article.get("en", [])):
                continue
            translated = b.translate_cached(article["en"][index])
            if not translated.strip():
                remaining += 1
                continue
            article["zh"][index] = translated
            repaired += 1
            changed = True
            b.atomic_write_text(
                data_path,
                json.dumps(article, ensure_ascii=False, indent=2),
            )

        if changed:
            print(f"{article['id']} repaired", flush=True)

    print(f"repaired: {repaired}, still empty: {remaining}")


if __name__ == "__main__":
    main()
