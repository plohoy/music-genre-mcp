| source | purpose | interface | license | expected size | required | risk |
|---|---|---|---|---:|---|---|
| MusicBrainz | canonical genre vocabulary and IDs | `/ws/2/genre/all` | core data CC0 | ~2,201 rows | yes | API rate limits |
| Wikidata | identifiers, aliases, explicit graph relations | API/SPARQL | CC0 | filtered query | yes | ambiguity and SPARQL availability |
| Wikipedia | short textual evidence only | REST/API | CC BY-SA | selected pages | optional | attribution and ambiguous pages |
| AcousticBrainz | empirical audio aggregates | downloadable dumps | CC0 | very large, 29M+ submissions | optional | genre join coverage and disk cost |
| FMA | hierarchy and cross-validation | metadata ZIP | dataset metadata ~342 MiB | 163 genres | optional | limited vocabulary and old snapshot |

