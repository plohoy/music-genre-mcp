#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from music_genres.tempo import aggregate_tempo_rows

result=aggregate_tempo_rows([
 ('trip hop',60),('trip hop',70),('trip hop',80),('trip hop',90),('trip hop',100),
 ('trip hop',0),('trip hop',999),('ambient','bad'),('techno',130),
])
t=result['genres']['trip hop']
assert t['bpm_min_observed']==60 and t['bpm_max_observed']==100
assert t['bpm_median']==80 and t['bpm_p10']==60 and t['bpm_p90']==100
assert t['sample_count']==5 and result['rejected']==3
assert result['genres']['techno']['bpm_median']==130
assert aggregate_tempo_rows([])['genres']=={}
print('ok')

