#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from music_genres.repository import connect, ensure_database
ensure_database()
with connect() as db:
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("SELECT count(*) FROM genres").fetchone()[0] >= 10
    assert db.execute("SELECT count(*) FROM generator_profiles WHERE source_id IS NULL").fetchone()[0] == 0
print("ok")

