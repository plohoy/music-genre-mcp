#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from music_genres.repository import ensure_database, resolve, search, build_style_prompt

ensure_database()
assert resolve("drum and baas")["canonical_name"] == "drum and bass"
assert resolve("трип-хоп")["canonical_name"] == "trip hop"
assert resolve("индастриал техно")["canonical_name"] == "industrial techno"
assert resolve("progressive house")["generation_ready"] is True
assert build_style_prompt(["progressive house"])["key_hint"] is None
assert resolve("not-a-real-genre")["status"] == "not_found"
assert resolve("not-a-real-genre").get("bpm_hint") is None
assert "1990s Bristol trip-hop" in build_style_prompt(["trip-hop"])["prompt"]
assert "no boom-bap" in build_style_prompt(["trip-hop"])["prompt"]
blend = build_style_prompt(["IDM", "ambient"], [0.6, 0.4])
assert blend["status"] == "ok" and blend["bpm_hint"] is None
assert build_style_prompt(["IDM", "invented-core"])["status"] == "not_found"
print("ok")
