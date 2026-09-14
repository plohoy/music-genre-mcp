from mcp.server.fastmcp import FastMCP
from .repository import build_style_prompt, ensure_database, related, resolve, search

mcp = FastMCP("music-genres", instructions="Resolve genres from the local evidence-backed database. Never invent an unknown genre or default profile.")

@mcp.tool()
def get_genre(name: str) -> dict:
    """Resolve a canonical genre or alias; returns not_found for unknown input."""
    return resolve(name)

@mcp.tool()
def search_genres(query: str, limit: int = 10) -> dict:
    """Search canonical genre names and aliases."""
    return search(query, limit)

@mcp.tool()
def list_genres(offset: int = 0, limit: int = 50) -> dict:
    """List locally available canonical genres."""
    from .repository import connect
    ensure_database()
    with connect() as conn:
        total = conn.execute("SELECT count(*) FROM genres").fetchone()[0]
        rows = conn.execute("SELECT name FROM genres ORDER BY name LIMIT ? OFFSET ?", (max(1,min(limit,200)),max(0,offset))).fetchall()
    return {"status":"ok","total":total,"genres":[r[0] for r in rows]}

@mcp.tool()
def related_genres(name: str, limit: int = 10) -> dict:
    """Return explicit relations only; an empty list means no stored evidence."""
    return related(name, limit)

@mcp.tool()
def mix_genres(genres: list[str], weights: list[float] | None = None) -> dict:
    """Resolve an explicit multi-genre blend without adding unstated genres."""
    return build_style_prompt(genres, weights)

@mcp.tool()
def build_generator_style_prompt(genres: list[str], weights: list[float] | None = None, extras: str = "") -> dict:
    """Build a deterministic YuE2 style prompt from resolved local profiles."""
    return build_style_prompt(genres, weights, extras)

def main() -> None:
    ensure_database()
    mcp.run()


if __name__ == "__main__":
    main()
