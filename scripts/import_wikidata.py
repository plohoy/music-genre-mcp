#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from music_genres.import_wikidata import run
p=argparse.ArgumentParser(); p.add_argument('--refresh',action='store_true'); a=p.parse_args()
print(json.dumps(run(a.refresh),indent=2))

