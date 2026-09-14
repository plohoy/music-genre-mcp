#!/usr/bin/env python3
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from music_genres.repository import build_database, connect
from music_genres.import_musicbrainz import import_snapshot

with tempfile.TemporaryDirectory() as temp:
    temp = Path(temp)
    db = temp / "test.db"
    snapshot = temp / "musicbrainz.json"
    snapshot.write_text(json.dumps({
        "provider":"MusicBrainz", "retrieved_at":"2026-09-14T00:00:00+00:00",
        "endpoint":"https://musicbrainz.org/ws/2/genre/all", "count":2,
        "genres":[
            {"id":"mb-ambient","name":"ambient","disambiguation":""},
            {"id":"mb-jazz","name":"jazz","disambiguation":""},
        ],
    }), encoding="utf-8")
    build_database(db)
    os.environ["MUSIC_GENRES_DB"] = str(db)
    first = import_snapshot(snapshot)
    second = import_snapshot(snapshot)
    assert first["inserted"] == 1 and first["updated"] == 1
    assert first["total"] == second["total"]
    with connect() as conn:
        assert conn.execute("SELECT musicbrainz_id FROM genres WHERE normalized_name='ambient'").fetchone()[0] == "mb-ambient"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    from music_genres.repository import resolve, build_style_prompt
    assert resolve("jazz")["generation_ready"] is False
    assert build_style_prompt(["jazz"])["status"] == "unsupported_for_generation"
print("ok")
