# AcousticBrainz feasibility

The downloadable corpus is keyed by MusicBrainz recording MBID and includes
low-level rhythm fields such as BPM. A technically valid genre aggregation
therefore requires a separate recording-MBID → genre association from
MusicBrainz. The join is feasible, but coverage and tag bias must be measured
before statistics are exposed. The corpus contains more than 29 million
submissions, so ingestion must stream and retain aggregates rather than raw
rows. It is not part of the lightweight runtime database.

