# Sources and evidence policy

The first production slice separates canonical vocabulary from generator
recommendations.

- MusicBrainz genre vocabulary/API: canonical spelling and future ID import;
  core data is CC0. https://musicbrainz.org/doc/About/Data_License
- Wikidata: future aliases and relationships; structured data is CC0.
  https://www.wikidata.org/wiki/Wikidata:Licensing
- AcousticBrainz: future empirical BPM distributions joined by MusicBrainz
  recording ID; released data is CC0. https://acousticbrainz.org/download
- FMA: optional validation corpus with a 163-genre hierarchy.
  https://github.com/mdeff/fma
- `local-compat-v1`: existing generator settings previously used by this
  installation. These are explicitly marked `heuristic`, never represented as
  measured genre statistics.

No copyrighted article text is stored.  A later ingestion stage may store
short evidence excerpts and hashes, subject to the source licence.

