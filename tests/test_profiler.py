#!/usr/bin/env python3
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from music_genres.profiler import extract_bpm_hint, extract_controlled_descriptors
from music_genres.repository import build_database, connect, list_profile_requests, profile_status, resolve

text='A music genre using a four-on-the-floor rhythm, synthesizers and gradual development. It runs between 120 and 130 bpm.'
values=extract_controlled_descriptors(text)
assert {(v['category'],v['value']) for v in values} >= {('rhythm','four-on-the-floor'),('instrumentation','synthesizers'),('arrangement','gradual development')}
assert extract_bpm_hint(text)==125
assert extract_bpm_hint('No tempo evidence here.') is None
print('ok')

with tempfile.TemporaryDirectory() as directory:
    db = Path(directory) / "genres.db"
    build_database(db)
    previous = os.environ.get("MUSIC_GENRES_DB")
    os.environ["MUSIC_GENRES_DB"] = str(db)
    try:
        result = resolve("trip-hop")
        assert result["status"] == "ok"
        assert result["generation_ready"] is True
        # Seed profile is ready, so it must not enter the enrichment queue.
        assert list_profile_requests()["requests"] == []
        with connect(db) as conn:
            conn.execute(
                "DELETE FROM generator_profiles WHERE genre_id=(SELECT id FROM genres WHERE normalized_name='trip hop')"
            )
            conn.commit()
        queued = resolve("trip-hop")
        assert queued["generation_ready"] is False
        assert list_profile_requests()["requests"][0]["genre"] == "trip hop"
        before = list_profile_requests()["requests"][0]["request_count"]
        assert profile_status("trip-hop")["profiling"]["status"] == "pending"
        assert list_profile_requests()["requests"][0]["request_count"] == before
        unknown = resolve("definitely-not-a-real-genre")
        assert unknown["status"] == "not_found"
        assert profile_status("definitely-not-a-real-genre")["status"] == "not_found"
    finally:
        if previous is None:
            os.environ.pop("MUSIC_GENRES_DB", None)
        else:
            os.environ["MUSIC_GENRES_DB"] = previous
