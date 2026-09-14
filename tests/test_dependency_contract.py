import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mcp_dependency_stays_on_fastmcp_compatible_major() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    assert "mcp>=1,<2" in dependencies
