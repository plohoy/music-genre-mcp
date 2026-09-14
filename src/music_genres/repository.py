from __future__ import annotations

import difflib
import json
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "music_genres.db"
DEFAULT_SEED = Path(__file__).with_name("data") / "seed_profiles.json"


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    value = re.sub(r"[_‐‑–—-]+", " ", value)
    return re.sub(r"\s+", " ", value)


def connect(path: Path | None = None) -> sqlite3.Connection:
    db = path or Path(os.environ.get("MUSIC_GENRES_DB", DEFAULT_DB))
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def build_database(db_path: Path = DEFAULT_DB, seed_path: Path = DEFAULT_SEED) -> None:
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript("""
      PRAGMA foreign_keys=ON;
      CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE sources(id TEXT PRIMARY KEY,provider TEXT NOT NULL,source_type TEXT NOT NULL,url TEXT NOT NULL,license TEXT NOT NULL,retrieved_at TEXT NOT NULL,snapshot_hash TEXT,metadata_json TEXT NOT NULL DEFAULT '{}');
      CREATE TABLE genres(id INTEGER PRIMARY KEY,slug TEXT UNIQUE NOT NULL,name TEXT UNIQUE NOT NULL,normalized_name TEXT UNIQUE NOT NULL,description TEXT,musicbrainz_id TEXT UNIQUE,wikidata_id TEXT,wikipedia_title TEXT,confidence REAL NOT NULL DEFAULT 0.5,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
      CREATE TABLE aliases(id INTEGER PRIMARY KEY,alias TEXT NOT NULL,normalized_alias TEXT UNIQUE NOT NULL,genre_id INTEGER NOT NULL REFERENCES genres(id),language TEXT,source_id TEXT REFERENCES sources(id),confidence REAL NOT NULL DEFAULT 0.5);
      CREATE TABLE descriptors(id INTEGER PRIMARY KEY,genre_id INTEGER NOT NULL REFERENCES genres(id),category TEXT NOT NULL,value TEXT NOT NULL,normalized_value TEXT NOT NULL,weight REAL NOT NULL DEFAULT 1.0,source_id TEXT NOT NULL REFERENCES sources(id),confidence REAL NOT NULL,UNIQUE(genre_id,category,normalized_value,source_id));
      CREATE TABLE generator_profiles(genre_id INTEGER PRIMARY KEY REFERENCES genres(id),generator TEXT NOT NULL,bpm_hint INTEGER,key_hint TEXT,scale_hint TEXT,source_id TEXT NOT NULL REFERENCES sources(id),confidence TEXT NOT NULL);
      CREATE TABLE relations(genre_id INTEGER NOT NULL REFERENCES genres(id),related_genre_id INTEGER NOT NULL REFERENCES genres(id),relation_type TEXT NOT NULL CHECK(relation_type IN ('parent','child','related','influenced_by','fusion_of','derived_from')),weight REAL NOT NULL DEFAULT 1.0,source_id TEXT NOT NULL REFERENCES sources(id),confidence REAL NOT NULL,CHECK(genre_id<>related_genre_id),PRIMARY KEY(genre_id,related_genre_id,relation_type,source_id));
      CREATE TABLE tempo_stats(id INTEGER PRIMARY KEY,genre_id INTEGER NOT NULL REFERENCES genres(id),bpm_min_observed REAL,bpm_p10 REAL,bpm_p25 REAL,bpm_median REAL,bpm_p75 REAL,bpm_p90 REAL,bpm_max_observed REAL,sample_count INTEGER NOT NULL,source_id TEXT NOT NULL REFERENCES sources(id),confidence REAL NOT NULL,UNIQUE(genre_id,source_id));
      CREATE TABLE evidence(id INTEGER PRIMARY KEY,genre_id INTEGER NOT NULL REFERENCES genres(id),source_id TEXT NOT NULL REFERENCES sources(id),evidence_type TEXT NOT NULL,text TEXT,structured_json TEXT NOT NULL DEFAULT '{}',confidence REAL NOT NULL);
      CREATE INDEX idx_alias_genre ON aliases(genre_id);
      CREATE INDEX idx_descriptor_genre ON descriptors(genre_id);
      CREATE INDEX idx_evidence_genre ON evidence(genre_id);
      CREATE INDEX idx_relation_related ON relations(related_genre_id);
    """)
    conn.execute("INSERT INTO metadata VALUES('schema_version',?)", (str(data["schema_version"]),))
    now = datetime.now(timezone.utc).isoformat()
    for source in data["sources"]:
        conn.execute(
            "INSERT INTO sources(id,provider,source_type,url,license,retrieved_at,metadata_json) VALUES(?,?,?,?,?,?,?)",
            (source["id"], source["title"], source["kind"], source["url"], source["license"], now, "{}"),
        )
    source_id = data["sources"][0]["id"]
    for item in data["genres"]:
        normalized_name = normalize(item["name"])
        slug = normalized_name.replace(" ", "-")
        cur = conn.execute(
            "INSERT INTO genres(slug,name,normalized_name,confidence,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (slug, item["name"], normalized_name, 0.6 if item["confidence"] == "medium" else 0.4, now, now),
        )
        genre_id = cur.lastrowid
        for alias in item.get("aliases", []):
            conn.execute(
                "INSERT OR IGNORE INTO aliases(alias,normalized_alias,genre_id,source_id,confidence) VALUES(?,?,?,?,?)",
                (alias, normalize(alias), genre_id, source_id, 0.7),
            )
        for value in item.get("descriptors", []):
            conn.execute(
                "INSERT INTO descriptors(genre_id,category,value,normalized_value,source_id,confidence) VALUES(?,?,?,?,?,?)",
                (genre_id, "production", value, normalize(value), source_id, 0.6 if item["confidence"] == "medium" else 0.4),
            )
        conn.execute("INSERT INTO generator_profiles VALUES(?,?,?,?,?,?,?)", (genre_id,"yue2",item.get("bpm"),item.get("key"),item.get("scale"),source_id,item["confidence"]))
    conn.commit()
    conn.close()


def ensure_database() -> Path:
    path = Path(os.environ.get("MUSIC_GENRES_DB", DEFAULT_DB))
    if not path.exists():
        build_database(path)
    return path


def all_names(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT name FROM genres UNION SELECT alias FROM aliases ORDER BY 1")]


def resolve(query: str) -> dict:
    ensure_database()
    with connect() as conn:
        key = normalize(query)
        row = conn.execute("""
          SELECT g.id,g.name,g.confidence genre_confidence,
                 p.bpm_hint,p.key_hint,p.scale_hint,p.confidence profile_confidence,
                 COALESCE(ps.id,ms.id) source_id,COALESCE(ps.url,ms.url) source_url,
                 CASE WHEN p.genre_id IS NULL THEN 0 ELSE 1 END generation_ready
          FROM genres g
          LEFT JOIN generator_profiles p ON p.genre_id=g.id
          LEFT JOIN sources ps ON ps.id=p.source_id
          LEFT JOIN sources ms ON ms.id='musicbrainz-genre-all'
          WHERE g.normalized_name=? OR g.id=(SELECT genre_id FROM aliases WHERE normalized_alias=?)
        """, (key,key)).fetchone()
        if not row:
            suggestions = difflib.get_close_matches(query, all_names(conn), n=5, cutoff=.45)
            return {"status":"not_found","query":query,"suggestions":suggestions}
        descriptor_rows = conn.execute(
            "SELECT category,value,weight,source_id,confidence FROM descriptors WHERE genre_id=? ORDER BY category,id",
            (row["id"],),
        ).fetchall()
        descriptors = [r["value"] for r in descriptor_rows]
        aliases = [dict(r) for r in conn.execute(
            "SELECT alias,language,source_id,confidence FROM aliases WHERE genre_id=? ORDER BY confidence DESC,alias",
            (row["id"],),
        )]
        relations = [dict(r) for r in conn.execute("""
            SELECT r.relation_type,g.name related_genre,r.weight,r.source_id,r.confidence
            FROM relations r JOIN genres g ON g.id=r.related_genre_id
            WHERE r.genre_id=? ORDER BY r.relation_type,g.name
        """, (row["id"],))]
        tempo_rows = [dict(r) for r in conn.execute("""
            SELECT bpm_min_observed,bpm_p10,bpm_p25,bpm_median,bpm_p75,bpm_p90,
                   bpm_max_observed,sample_count,source_id,confidence
            FROM tempo_stats WHERE genre_id=? ORDER BY confidence DESC,sample_count DESC
        """, (row["id"],))]
        return {
            "status":"ok", "query":query, "canonical_name":row["name"],
            "generation_ready":bool(row["generation_ready"]),
            "bpm_hint":row["bpm_hint"], "key_hint":row["key_hint"],
            "scale_hint":row["scale_hint"], "descriptors":descriptors,
            "descriptor_records":[dict(r) for r in descriptor_rows],
            "aliases":aliases, "relations":relations, "tempo_stats":tempo_rows,
            "confidence":row["profile_confidence"] or row["genre_confidence"],
            "source":{"id":row["source_id"],"url":row["source_url"]},
        }


def related(name: str, limit: int = 10) -> dict:
    profile = resolve(name)
    if profile["status"] != "ok":
        return profile
    return {
        "status":"ok", "genre":profile["canonical_name"],
        "relations":profile["relations"][:max(1,min(limit,100))],
    }


def search(query: str, limit: int = 10) -> dict:
    ensure_database()
    needle = normalize(query)
    with connect() as conn:
        rows = conn.execute("""SELECT DISTINCT g.name FROM genres g LEFT JOIN aliases a ON a.genre_id=g.id WHERE g.normalized_name LIKE ? OR a.normalized_alias LIKE ? ORDER BY g.name LIMIT ?""", (f"%{needle}%",f"%{needle}%",max(1,min(limit,50)))).fetchall()
        names = [r[0] for r in rows]
        if not names:
            names = difflib.get_close_matches(query, all_names(conn), n=max(1,min(limit,10)), cutoff=.35)
        return {"status":"ok","query":query,"matches":names}


def build_style_prompt(genres: list[str], weights: list[float] | None = None, extras: str = "") -> dict:
    if not genres:
        return {"status":"error","error":"at least one genre is required"}
    profiles = [resolve(name) for name in genres]
    missing = [p for p in profiles if p["status"] != "ok"]
    if missing:
        return {"status":"not_found","unresolved":missing}
    unsupported = [p["canonical_name"] for p in profiles if not p["generation_ready"]]
    if unsupported:
        return {
            "status":"unsupported_for_generation",
            "genres":unsupported,
            "error":"genre is canonical but has no evidence-backed generator profile",
        }
    if weights and len(weights) != len(profiles):
        return {"status":"error","error":"weights length must match genres length"}
    names = [p["canonical_name"] for p in profiles]
    tags = []
    for p in profiles:
        tags.extend(p["descriptors"])
    bpm = profiles[0]["bpm_hint"] if len(profiles) == 1 else None
    key = profiles[0]["key_hint"] if len(profiles) == 1 else None
    scale = profiles[0]["scale_hint"] if len(profiles) == 1 else None
    parts = [" + ".join(names), *dict.fromkeys(tags)]
    if bpm: parts.append(f"{bpm} BPM")
    if key and scale: parts.append(f"{key} {scale}")
    if extras.strip(): parts.append(extras.strip())
    return {"status":"ok","genres":names,"prompt":", ".join(parts),"bpm_hint":bpm,"key_hint":key,"scale_hint":scale,"profiles":profiles}
