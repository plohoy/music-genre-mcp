#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from music_genres.profiler import enrich_genre
from music_genres.repository import list_profile_requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich queued genre profiles, highest demand first")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--review-only", action="store_true")
    args = parser.parse_args()
    queued = list_profile_requests(args.limit)["requests"]
    results = []
    for request in queued:
        if request["status"] != "pending":
            continue
        results.append(enrich_genre(request["genre"], auto_approve=not args.review_only))
    print(json.dumps({"status": "ok", "processed": len(results), "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
