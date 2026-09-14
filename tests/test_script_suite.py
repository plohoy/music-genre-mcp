import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_TESTS = sorted((ROOT / "tests").glob("test_*.py"))
SCRIPT_TESTS = [path for path in SCRIPT_TESTS if path.name not in {"test_dependency_contract.py", "test_script_suite.py"}]


@pytest.mark.parametrize("script", SCRIPT_TESTS, ids=lambda path: path.stem)
def test_legacy_script_contracts(script: Path) -> None:
    subprocess.run([sys.executable, str(script)], cwd=ROOT, check=True)
