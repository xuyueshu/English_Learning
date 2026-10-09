#!/usr/bin/env python3
"""Generate manifest.json from the per-article JSON data files."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MANIFEST = ROOT / "manifest.json"


def main():
    articles = []
    for path in sorted(DATA_DIR.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        articles.append(
            {
                "id": article["id"],
                "title": article["title"],
                "date": article["date"],
            }
        )

    articles.sort(key=lambda item: item["date"], reverse=True)
    MANIFEST.write_text(
        json.dumps(articles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"manifest entries: {len(articles)}")


if __name__ == "__main__":
    main()
