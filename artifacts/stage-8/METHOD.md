# Empirical tempo aggregation method

Status: synthetic pipeline PASS; real AcousticBrainz aggregation pending the
recording-MBID → MusicBrainz genre coverage audit.

Rows are streamed into a temporary SQLite database, so the Python process does
not retain the complete corpus in memory. BPM outside 30–300 is rejected.
Observed half/double-time values are deliberately not rewritten: percentiles
expose a broad or multimodal distribution instead of fabricating certainty.
The stored output contains min, p10, p25, median, p75, p90, max, sample count,
source and confidence. Raw millions of track features are not copied into the
runtime MCP database.
