from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .repository import DEFAULT_DB, ROOT, connect, ensure_database, normalize

API = "https://musicbrainz.org/ws/2/genre/all"
USER_AGENT = "hermes-music-genres-mcp/0.2 (local genre knowledge base)"
SNAPSHOT = ROOT / "data" / "snapshots" / "musicbrainz-genres.json"


def fetch_json(url: str, retries: int = 3) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except Exception:
            if attempt + 1 == retries:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def download_snapshot(path: Path = SNAPSHOT, delay: float = 1.05) -> dict:
    genres: list[dict] = []
    offset = 0
    total = None
    while total is None or offset < total:
        payload = fetch_json(f"{API}?limit=100&offset={offset}&fmt=json")
        page = payload.get("genres", [])
        genres.extend(page)
        total = int(payload.get("genre-count", len(genres)))
        offset += len(page)
        if not page:
            break
        if offset < total:
            time.sleep(delay)
    snapshot = {"provider":"MusicBrainz","retrieved_at":datetime.now(timezone.utc).isoformat(),"endpoint":API,"count":len(genres),"genres":genres}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def import_snapshot(path: Path = SNAPSHOT) -> dict:
    ensure_database()
    raw = path.read_bytes()
    snapshot = json.loads(raw)
    source_id = "musicbrainz-genre-all"
    now = snapshot["retrieved_at"]
    inserted = updated = 0
    with connect() as conn:
        conn.execute(
            """INSERT INTO sources(id,provider,source_type,url,license,retrieved_at,snapshot_hash,metadata_json)
               VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET retrieved_at=excluded.retrieved_at,snapshot_hash=excluded.snapshot_hash,metadata_json=excluded.metadata_json""",
            (source_id,"MusicBrainz","canonical vocabulary",snapshot["endpoint"],"CC0",now,hashlib.sha256(raw).hexdigest(),json.dumps({"count":snapshot["count"]})),
        )
        for item in snapshot["genres"]:
            name = item["name"].strip()
            key = normalize(name)
            existing = conn.execute("SELECT id,musicbrainz_id FROM genres WHERE normalized_name=?", (key,)).fetchone()
            if existing:
                conn.execute("UPDATE genres SET musicbrainz_id=?,updated_at=?,confidence=MAX(confidence,0.95) WHERE id=?", (item["id"],now,existing["id"]))
                updated += 1
            else:
                base_slug = key.replace(" ", "-")
                slug = base_slug
                suffix = 2
                while conn.execute("SELECT 1 FROM genres WHERE slug=?", (slug,)).fetchone():
                    slug = f"{base_slug}-{suffix}"; suffix += 1
                conn.execute("INSERT INTO genres(slug,name,normalized_name,musicbrainz_id,confidence,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (slug,name,key,item["id"],0.95,now,now))
                inserted += 1
        conn.commit()
        total = conn.execute("SELECT count(*) FROM genres").fetchone()[0]
    return {"inserted":inserted,"updated":updated,"total":total,"snapshot_count":snapshot["count"]}


def run(refresh: bool = False) -> dict:
    if refresh or not SNAPSHOT.exists():
        download_snapshot()
    return import_snapshot()

