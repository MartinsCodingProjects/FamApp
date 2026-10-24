import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    """A scratch root with the real shared/ sources, so tools can be run against broken copies."""
    shutil.copytree(REPO / "shared", tmp_path / "shared")
    return tmp_path
