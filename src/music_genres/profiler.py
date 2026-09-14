from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .import_wikidata import API as WIKIDATA_API, USER_AGENT, exact_candidate
from .repository import DEFAULT_DB, connect, ensure_database, normalize

VOCAB_PATH = Path(__file__).with_name("data") / "controlled_vocabulary.json"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"


def fetch_json(base_url: str, params: dict[str, str], retries: int = 5) -> dict:
    url = base_url + "?" + urllib.parse.urlencode({**params, "format":"json", "origin":"*"})
    request = urllib.request.Request(url, headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 429 and attempt + 1 < retries:
                time.sleep(5 * (attempt + 1)); continue
            raise
        except Exception:
            if attempt + 1 == retries: raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def extract_controlled_descriptors(text: str) -> list[dict]:
    vocabulary = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    folded = text.casefold(); descriptors=[]
    for category, values in vocabulary.items():
        for descriptor, markers in values.items():
            hits = [marker for marker in markers if marker.casefold() in folded]
            if hits:
                descriptors.append({"category":category,"value":descriptor,"matched":hits,"confidence":0.75})
    return descriptors


def extract_bpm_hint(text: str) -> int | None:
    patterns = (
        r"(?:between|from)\s+(\d{2,3})\s+(?:and|to|–|—|-)\s+(\d{2,3})\s+(?:beats per minute|bpm)",
        r"(\d{2,3})\s*(?:–|—|-)\s*(\d{2,3})\s*(?:beats per minute|bpm)",
    )
    for pattern in patterns:
        match = re.search(pattern,text.casefold())
        if match:
            low,high=map(int,match.groups())
            if 40 <= low <= high <= 240: return round((low+high)/2)
    return None


def resolve_wikidata(name: str, aliases: list[str]) -> tuple[dict | None,str]:
    for query in [name,*aliases[:6]]:
        payload=fetch_json(WIKIDATA_API,{"action":"wbsearchentities","search":query,"language":"en","uselang":"en","type":"item","limit":"10"})
        candidate,status=exact_candidate(query,payload.get("search",[]))
        if candidate or status=="ambiguous": return candidate,status
        time.sleep(1.1)
    return None,"unmapped"


def wikipedia_evidence(qid: str) -> dict:
    entity_payload=fetch_json(WIKIDATA_API,{"action":"wbgetentities","ids":qid,"props":"sitelinks","sitefilter":"enwiki"})
    title=entity_payload.get("entities",{}).get(qid,{}).get("sitelinks",{}).get("enwiki",{}).get("title")
    if not title: return {"status":"no_wikipedia_sitelink"}
    payload=fetch_json(WIKIPEDIA_API,{"action":"query","prop":"extracts|info","inprop":"url","explaintext":"1","redirects":"1","titles":title})
    page=next(iter(payload.get("query",{}).get("pages",{}).values()),{})
    if page.get("missing") is not None or not page.get("extract"): return {"status":"no_evidence","title":title}
    text=page["extract"][:12000]
    return {"status":"ok","title":page.get("title",title),"pageid":page.get("pageid"),"url":page.get("fullurl",f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ','_'))}"),"text":text}


def enrich_genre(name: str, *, auto_approve: bool = True) -> dict:
    ensure_database()
    now=datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        genre=conn.execute("SELECT id,name,wikidata_id FROM genres WHERE normalized_name=?",(normalize(name),)).fetchone()
        if not genre: return {"status":"not_found","genre":name}
        aliases=[r[0] for r in conn.execute("SELECT alias FROM aliases WHERE genre_id=? AND (language IS NULL OR language='en')",(genre["id"],)) if r[0].isascii()]
        conn.execute("INSERT INTO profile_requests(genre_id,request_count,first_requested_at,last_requested_at,status) VALUES(?,1,?,?,'processing') ON CONFLICT(genre_id) DO UPDATE SET status='processing',last_requested_at=excluded.last_requested_at",(genre["id"],now,now)); conn.commit()
        qid=genre["wikidata_id"]
    if not qid:
        candidate,mapping_status=resolve_wikidata(genre["name"],aliases)
        if not candidate:
            _fail(genre["id"],"needs_review",f"Wikidata mapping: {mapping_status}")
            return {"status":"needs_review","genre":genre["name"],"reason":f"Wikidata mapping: {mapping_status}"}
        qid=candidate["id"]
    evidence=wikipedia_evidence(qid)
    if evidence["status"]!="ok":
        _fail(genre["id"],"needs_review",evidence["status"])
        return {"status":"needs_review","genre":genre["name"],"reason":evidence["status"]}
    descriptors=extract_controlled_descriptors(evidence["text"])
    categories={d["category"] for d in descriptors}; bpm=extract_bpm_hint(evidence["text"])
    checks={"exact_wikidata":True,"wikipedia_page":evidence["title"],"descriptor_count":len(descriptors),"category_count":len(categories),"minimum_descriptors":len(descriptors)>=3,"minimum_categories":len(categories)>=2}
    approved=auto_approve and all((checks["minimum_descriptors"],checks["minimum_categories"]))
    source_id=f"wikipedia-{qid.casefold()}"; raw=evidence["text"].encode()
    with connect() as conn:
        conn.execute("INSERT INTO sources(id,provider,source_type,url,license,retrieved_at,snapshot_hash,metadata_json) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET retrieved_at=excluded.retrieved_at,snapshot_hash=excluded.snapshot_hash,metadata_json=excluded.metadata_json",(source_id,"Wikipedia","textual evidence",evidence["url"],"CC BY-SA 4.0",now,hashlib.sha256(raw).hexdigest(),json.dumps({"pageid":evidence["pageid"],"title":evidence["title"]})))
        conn.execute("UPDATE genres SET wikidata_id=?,wikipedia_title=?,updated_at=? WHERE id=?",(qid,evidence["title"],now,genre["id"]))
        cur=conn.execute("INSERT INTO evidence(genre_id,source_id,evidence_type,text,structured_json,confidence) VALUES(?,?,?,?,?,?)",(genre["id"],source_id,"wikipedia extract",evidence["text"],json.dumps({"pageid":evidence["pageid"]}),0.8)); evidence_id=cur.lastrowid
        for descriptor in descriptors:
            cur=conn.execute("INSERT OR IGNORE INTO descriptors(genre_id,category,value,normalized_value,weight,source_id,confidence) VALUES(?,?,?,?,?,?,?)",(genre["id"],descriptor["category"],descriptor["value"],normalize(descriptor["value"]),1.0,source_id,descriptor["confidence"]))
            row=conn.execute("SELECT id FROM descriptors WHERE genre_id=? AND category=? AND normalized_value=? AND source_id=?",(genre["id"],descriptor["category"],normalize(descriptor["value"]),source_id)).fetchone()
            conn.execute("INSERT OR IGNORE INTO descriptor_evidence VALUES(?,?)",(row["id"],evidence_id))
        status="approved" if approved else "needs_review"
        conn.execute("INSERT INTO profile_candidates(genre_id,status,category_count,descriptor_count,source_id,validation_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(genre_id) DO UPDATE SET status=excluded.status,category_count=excluded.category_count,descriptor_count=excluded.descriptor_count,source_id=excluded.source_id,validation_json=excluded.validation_json,updated_at=excluded.updated_at",(genre["id"],status,len(categories),len(descriptors),source_id,json.dumps(checks),now,now))
        if approved:
            conn.execute("INSERT INTO generator_profiles(genre_id,generator,bpm_hint,key_hint,scale_hint,source_id,confidence) VALUES(?,?,?,?,?,?,?) ON CONFLICT(genre_id) DO UPDATE SET bpm_hint=excluded.bpm_hint,key_hint=NULL,scale_hint=NULL,source_id=excluded.source_id,confidence=excluded.confidence",(genre["id"],"yue2",bpm,None,None,source_id,"medium"))
        conn.execute("UPDATE profile_requests SET status=?,last_error=NULL WHERE genre_id=?",("ready" if approved else "needs_review",genre["id"]))
        conn.commit()
    return {"status":"ready" if approved else "needs_review","genre":genre["name"],"wikidata_id":qid,"wikipedia_title":evidence["title"],"descriptor_count":len(descriptors),"categories":sorted(categories),"bpm_hint":bpm,"checks":checks}


def _fail(genre_id: int, status: str, error: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE profile_requests SET status=?,last_error=? WHERE genre_id=?",
            (status, error, genre_id),
        )
        conn.commit()
