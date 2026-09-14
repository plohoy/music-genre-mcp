from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from .repository import ROOT, connect, ensure_database, normalize

API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "hermes-music-genres-mcp/0.2 (local genre knowledge base)"
SNAPSHOT = ROOT / "data" / "snapshots" / "wikidata-generator-genres.json"
MUSIC_MARKERS = ("music genre", "musical genre", "genre of music", "music style", "musical style", "subgenre")


def is_musical_description(value: str) -> bool:
    value = value.casefold()
    return any(marker in value for marker in MUSIC_MARKERS) or ("genre" in value and "music" in value)


def fetch(params: dict[str, str], retries: int = 5) -> dict:
    url = API + "?" + urllib.parse.urlencode({**params, "format":"json", "origin":"*"})
    request = urllib.request.Request(url, headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 429 and attempt + 1 < retries:
                retry_after = error.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else 5 * (attempt + 1))
                continue
            raise
        except Exception:
            if attempt + 1 == retries: raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def exact_candidate(name: str, results: list[dict]) -> tuple[dict | None, str]:
    key = normalize(name)
    musical = [r for r in results if is_musical_description(r.get("description", ""))]
    scored = []
    for item in musical:
        label = normalize(item.get("label", ""))
        match = normalize(item.get("match", {}).get("text", ""))
        aliases = {normalize(value) for value in item.get("aliases", [])}
        score = 0
        if label == key: score = 100
        elif match == key or key in aliases: score = 95
        elif label == f"{key} music" or (label.endswith(" music") and label[:-6] == key): score = 90
        if score: scored.append((score,item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1], "exact_musical" if scored[0][0] == 100 else "controlled_musical"
    if scored: return None, "ambiguous"
    return None, "unmapped"


def download_snapshot(path: Path = SNAPSHOT, delay: float = 1.1) -> dict:
    ensure_database()
    with connect() as conn:
        rows = conn.execute("""SELECT g.id,g.name FROM genres g JOIN generator_profiles p ON p.genre_id=g.id ORDER BY g.name""").fetchall()
        entries = []
        for row in rows:
            aliases = [r[0] for r in conn.execute(
                "SELECT alias FROM aliases WHERE genre_id=? AND (language IS NULL OR language='en') ORDER BY confidence DESC,id LIMIT 6",
                (row["id"],),
            ) if r[0].isascii()]
            entries.append((row["name"], aliases))
    mappings = []
    for name, aliases in entries:
        candidate = None; status = "unmapped"; lookup_query = name
        for query in [name, *aliases]:
            result = fetch({"action":"wbsearchentities","search":query,"language":"en","uselang":"en","type":"item","limit":"10"})
            candidate, status = exact_candidate(query, result.get("search", []))
            lookup_query = query
            time.sleep(delay)
            if candidate or status == "ambiguous": break
        mappings.append({"genre":name,"lookup_query":lookup_query,"status":status,"candidate":candidate})
    ids = [m["candidate"]["id"] for m in mappings if m["candidate"]]
    entities = {}
    if ids:
        entities = fetch({"action":"wbgetentities","ids":"|".join(ids),"props":"labels|aliases|descriptions|claims","languages":"en|ru"}).get("entities", {})
    snapshot = {"provider":"Wikidata","retrieved_at":datetime.now(UTC).isoformat(),"endpoint":API,"mappings":mappings,"entities":entities}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding="utf-8")
    return snapshot


def import_snapshot(path: Path = SNAPSHOT) -> dict:
    raw = path.read_bytes(); snapshot = json.loads(raw); now = snapshot["retrieved_at"]
    source_id = "wikidata-generator-genres"
    mapped = ambiguous = unmapped = aliases_added = relations_added = 0
    with connect() as conn:
        conn.execute("""INSERT INTO sources(id,provider,source_type,url,license,retrieved_at,snapshot_hash,metadata_json)
          VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET retrieved_at=excluded.retrieved_at,snapshot_hash=excluded.snapshot_hash,metadata_json=excluded.metadata_json""",
          (source_id,"Wikidata","identifier and graph enrichment",API,"CC0",now,hashlib.sha256(raw).hexdigest(),json.dumps({"scope":"generator profiles"})))
        for mapping in snapshot["mappings"]:
            if mapping["status"] == "ambiguous": ambiguous += 1; continue
            if not mapping["candidate"]: unmapped += 1; continue
            qid = mapping["candidate"]["id"]
            row = conn.execute("SELECT id FROM genres WHERE normalized_name=?",(normalize(mapping["genre"]),)).fetchone()
            if not row: unmapped += 1; continue
            conn.execute("UPDATE genres SET wikidata_id=?,updated_at=? WHERE id=?",(qid,now,row["id"])); mapped += 1
            entity = snapshot["entities"].get(qid,{})
            for lang, values in entity.get("aliases",{}).items():
                for value in values:
                    alias = value.get("value","").strip()
                    if alias:
                        before = conn.total_changes
                        conn.execute("INSERT OR IGNORE INTO aliases(alias,normalized_alias,genre_id,language,source_id,confidence) VALUES(?,?,?,?,?,?)",(alias,normalize(alias),row["id"],lang,source_id,0.9))
                        aliases_added += conn.total_changes - before
        # Only explicit P279 links whose parent is also confidently mapped.
        qid_to_genre = {r[1]:r[0] for r in conn.execute("SELECT id,wikidata_id FROM genres WHERE wikidata_id IS NOT NULL")}
        for qid, entity in snapshot["entities"].items():
            child = qid_to_genre.get(qid)
            if not child: continue
            for claim in entity.get("claims",{}).get("P279",[]):
                parent_qid = claim.get("mainsnak",{}).get("datavalue",{}).get("value",{}).get("id")
                parent = qid_to_genre.get(parent_qid)
                if parent and parent != child:
                    before = conn.total_changes
                    conn.execute("INSERT OR IGNORE INTO relations(genre_id,related_genre_id,relation_type,weight,source_id,confidence) VALUES(?,?,?,?,?,?)",(child,parent,"parent",1.0,source_id,0.95))
                    relations_added += conn.total_changes - before
        conn.commit()
    return {"mapped":mapped,"ambiguous":ambiguous,"unmapped":unmapped,"aliases_added":aliases_added,"relations_added":relations_added}


def run(refresh: bool = False) -> dict:
    if refresh or not SNAPSHOT.exists(): download_snapshot()
    return import_snapshot()
