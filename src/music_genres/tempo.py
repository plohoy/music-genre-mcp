from __future__ import annotations

import csv
import sqlite3
import tempfile
from collections.abc import Iterable
from pathlib import Path

PERCENTILES = ((0.10,"bpm_p10"),(0.25,"bpm_p25"),(0.50,"bpm_median"),(0.75,"bpm_p75"),(0.90,"bpm_p90"))


def _nearest_rank(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values: raise ValueError("empty distribution")
    index = max(0, min(len(sorted_values)-1, round(fraction*(len(sorted_values)-1))))
    return sorted_values[index]


def aggregate_tempo_rows(rows: Iterable[tuple[str, float]], temp_dir: Path | None = None) -> dict[str,dict]:
    """Aggregate arbitrary-size `(genre, bpm)` rows using disk-backed SQLite.

    Values outside 30..300 BPM are rejected as invalid. Half/double-time values
    are retained rather than silently transformed; ambiguity is visible in the
    returned distribution.
    """
    with tempfile.NamedTemporaryFile(suffix=".db",dir=temp_dir,delete=True) as handle:
        db=sqlite3.connect(handle.name)
        db.execute("CREATE TABLE observations(genre TEXT NOT NULL,bpm REAL NOT NULL)")
        accepted=rejected=0
        for genre,bpm in rows:
            try: value=float(bpm)
            except (TypeError,ValueError): rejected+=1; continue
            if not genre or not 30 <= value <= 300: rejected+=1; continue
            db.execute("INSERT INTO observations VALUES(?,?)",(genre,value)); accepted+=1
        db.commit(); result={}
        for (genre,) in db.execute("SELECT DISTINCT genre FROM observations ORDER BY genre"):
            values=[r[0] for r in db.execute("SELECT bpm FROM observations WHERE genre=? ORDER BY bpm",(genre,))]
            stats={"bpm_min_observed":values[0],"bpm_max_observed":values[-1],"sample_count":len(values)}
            stats.update({field:_nearest_rank(values,q) for q,field in PERCENTILES})
            result[genre]=stats
        db.close()
    return {"genres":result,"accepted":accepted,"rejected":rejected}


def read_genre_bpm_csv(path: Path, genre_column: str="genre", bpm_column: str="bpm"):
    with path.open(newline="",encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            yield row.get(genre_column,""),row.get(bpm_column,"")

