#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from music_genres.profiler import enrich_genre

parser = argparse.ArgumentParser()
parser.add_argument("genre")
parser.add_argument("--review-only", action="store_true")
args = parser.parse_args()
print(json.dumps(enrich_genre(args.genre, auto_approve=not args.review_only), ensure_ascii=False, indent=2))
