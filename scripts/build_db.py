#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from music_genres.repository import DEFAULT_DB, build_database

build_database()
print(DEFAULT_DB)

