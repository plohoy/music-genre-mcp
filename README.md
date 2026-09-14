# Music Genre MCP

An offline-first Model Context Protocol server for resolving music genres and
building deterministic prompts for music-generation models.

It prevents a common failure mode in agentic music systems: an unknown or
misspelled genre silently falling back to a generic prompt such as `120 BPM,
A minor`. Music Genre MCP resolves canonical names and aliases, tracks
provenance, and fails closed when a generator profile is unavailable.

## Features

- 2,201 canonical MusicBrainz genres and MBIDs in the included snapshot.
- Conservative Wikidata aliases and explicitly sourced genre relationships.
- Separate `known` and `generation_ready` states.
- Deterministic YuE2-oriented style prompts and explicit genre mixing.
- SQLite runtime with no network access.
- Provenance, confidence, evidence, relations, and empirical-tempo schema.
- No generic BPM, key, or genre fallback for unknown input.

## Installation

Python 3.11 or newer is required.

```bash
git clone https://github.com/plohoy/music-genre-mcp.git
cd music-genre-mcp
python3 -m venv .venv
./.venv/bin/pip install -e .
```

The repository includes a ready SQLite database and reproducible source
snapshots. To rebuild and reimport them without refreshing the network data:

```bash
python scripts/build_db.py
python scripts/import_musicbrainz.py
python scripts/import_wikidata.py
python scripts/validate_db.py
```

Add `--refresh` to an importer only when you intentionally want a fresh remote
snapshot.

## MCP configuration

Generic stdio configuration:

```json
{
  "mcpServers": {
    "music-genres": {
      "command": "/absolute/path/music-genre-mcp/.venv/bin/music-genres-mcp",
      "env": {
        "MUSIC_GENRES_DB": "/absolute/path/music-genre-mcp/data/music_genres.db"
      }
    }
  }
}
```

Hermes `config.yaml`:

```yaml
mcp_servers:
  music-genres:
    command: /absolute/path/music-genre-mcp/.venv/bin/music-genres-mcp
    env:
      MUSIC_GENRES_DB: /absolute/path/music-genre-mcp/data/music_genres.db
    enabled: true
    timeout: 30
```

Test the connection:

```bash
hermes mcp test music-genres
```

## MCP tools

| Tool | Purpose |
|---|---|
| `get_genre` | Resolve a name or alias and return its complete local profile. |
| `search_genres` | Search canonical names and aliases. |
| `list_genres` | Page through the local vocabulary. |
| `related_genres` | Return explicitly sourced genre relations. |
| `mix_genres` | Combine only the genres explicitly requested. |
| `build_generator_style_prompt` | Build a deterministic YuE2 style prompt. |

Unknown input returns `status: not_found`. A canonical genre without a curated
generator profile returns `status: unsupported_for_generation`.

## Command-line usage

```bash
music-genres get "trip-hop"
music-genres search "industrial techno"
music-genres prompt "industrial techno"
music-genres prompt idm ambient
```

Example prompt for `industrial techno`:

```text
industrial techno, dark industrial techno, relentless four-on-the-floor kick,
distorted warehouse percussion, metallic impacts, grinding bass, cold machine
drones, atonal analog stabs, hypnotic functional arrangement, raw underground
production, no trance melody, no EDM buildup, no trap, no dubstep, 138 BPM,
F minor
```

## Integration with music-generation models

### Recommended agent contract

1. Extract only genre names explicitly supplied by the user.
2. Call `build_generator_style_prompt`.
3. Stop on `not_found` or `unsupported_for_generation`; show suggestions.
4. Pass the returned `prompt` directly to the generator.
5. Apply explicit user BPM/key through native backend fields when available.
6. Never append an LLM-written reinterpretation after the resolved prompt; it
   can overpower the intended genre.

### YuE2

```python
import subprocess
from music_genres.repository import build_style_prompt

profile = build_style_prompt(["industrial techno"])
if profile["status"] != "ok":
    raise ValueError(profile)

subprocess.run([
    "python", "generate.py",
    "--model", "8bit",
    "--style", profile["prompt"],
    "--lyrics", "[Instrumental]",
    "--cot", "full",
    "--max-semantic-tokens", "1500",
    "--out", "industrial-techno.wav",
], check=True)
```

YuE2 treats textual BPM, key, and genre descriptors as conditioning rather
than hard constraints. With `--cot full`, its generated ABC plan may override
tempo or harmony. For strict musical structure, provide a reviewed external
ABC file or use a reference-audio workflow.

### MiniMax Music

```python
from music_genres.repository import build_style_prompt

profile = build_style_prompt(["trip-hop"])
style_prompt = profile["prompt"]

# Send style_prompt as the model's style/caption field.
# Send lyrics separately. For an instrumental request, use the backend's
# native instrumental/no-vocals control rather than relying only on prose.
```

Duration, instrumental mode, BPM, and key should remain separate API fields
whenever the backend exposes them.

### Generic HTTP generator

```python
import requests
from music_genres.repository import build_style_prompt

profile = build_style_prompt(["neurofunk drum and bass"])
if profile["status"] == "ok":
    response = requests.post(
        "http://127.0.0.1:9000/generate",
        json={
            "style": profile["prompt"],
            "instrumental": True,
            "duration_seconds": 60,
        },
        timeout=1800,
    )
    response.raise_for_status()
```

### Explicit genre blends

```python
profile = build_style_prompt(["idm", "ambient"], weights=[0.6, 0.4])
```

The MCP adds no third genre. BPM and key hints are omitted for blends because
choosing one genre's defaults would misrepresent the combined request.

## Data and provenance

The SQLite schema contains genres, aliases, relations, descriptors, generator
profiles, tempo distributions, sources, and evidence. Generator BPM/key values
are labelled heuristic and are not presented as empirical musicological truth.

Primary sources:

- [MusicBrainz](https://musicbrainz.org/doc/About/Data_License): canonical
  vocabulary and identifiers; core data is CC0.
- [Wikidata](https://www.wikidata.org/wiki/Wikidata:Licensing): aliases,
  identifiers, and explicit graph claims; structured data is CC0.
- [AcousticBrainz](https://acousticbrainz.org/download): planned empirical
  distributions after recording-to-genre coverage validation.
- [FMA](https://github.com/mdeff/fma): planned hierarchy and feature
  cross-validation.

See [`artifacts/`](artifacts/) for source, licence, feasibility, and method
reports.

## Development

```bash
./.venv/bin/pip install -e '.[dev]'
pytest
ruff check src tests scripts
python scripts/validate_db.py
```

The runtime server never contacts external services. Network access is needed
only when refreshing build-time snapshots.

## Lazy generator profiles

The catalogue can recognize far more genres than it can safely condition a
generator with. A lookup of a known genre without a reviewed generator profile
therefore returns `unsupported_for_generation` and atomically records demand in
`profile_requests`; it never falls back to a generic genre.

Inspect demand and status without network access:

```bash
music-genres profile-requests --limit 20
music-genres profile-status jazz
```

An administrator can enrich one requested genre, or a bounded demand-ordered
batch:

```bash
python scripts/enrich_profile.py jazz --review-only
python scripts/enrich_profile.py jazz
python scripts/enrich_pending.py --limit 10
```

Enrichment resolves an exact Wikidata entity, retrieves its English Wikipedia
article as attributed evidence, and extracts only descriptors from the checked-in
controlled vocabulary. A candidate is promoted only when validation finds at
least three supported descriptors spanning at least two categories. Explicit BPM
ranges are preserved; BPM, key, and scale remain unset when the evidence does not
state them. Ambiguous or thin evidence is stored as `needs_review`.

The MCP exposes `get_generator_profile_status` and
`list_generator_profile_requests`. Network enrichment is deliberately excluded
from the runtime MCP surface so an ordinary model call cannot mutate the genre
knowledge base from arbitrary web content.

## License

Project code is MIT licensed. Imported data keeps its original licence and
provenance; see `docs/SOURCES.md` and `artifacts/stage-0/licenses.md`.
