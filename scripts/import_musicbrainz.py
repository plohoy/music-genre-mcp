#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from music_genres.import_musicbrainz import run

p = argparse.ArgumentParser()
p.add_argument("--refresh", action="store_true")
args = p.parse_args()
print(json.dumps(run(args.refresh), indent=2))
