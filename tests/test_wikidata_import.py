#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from music_genres.import_wikidata import exact_candidate, is_musical_description

assert is_musical_description('genre of electronic music')
assert not is_musical_description('1993 studio album by Moby')

results=[
 {"id":"Q1","label":"ambient","description":"music genre","match":{"text":"ambient"}},
 {"id":"Q2","label":"Ambient","description":"software product","match":{"text":"Ambient"}},
]
candidate,status=exact_candidate("Ambient",results)
assert status=="exact_musical" and candidate["id"]=="Q1"
candidate,status=exact_candidate("Other",results)
assert candidate is None and status=="unmapped"
ambiguous=results+[ {"id":"Q3","label":"Ambient","description":"musical genre","match":{"text":"Ambient"}} ]
candidate,status=exact_candidate("ambient",ambiguous)
assert candidate is None and status=="ambiguous"
candidate,status=exact_candidate("ambient",[
 {"id":"Q10","label":"ambient music","description":"music genre","match":{"text":"ambient music"}},
 {"id":"Q11","label":"Ambient","description":"studio album","match":{"text":"Ambient"}},
])
assert candidate["id"]=="Q10" and status=="controlled_musical"
print('ok')
