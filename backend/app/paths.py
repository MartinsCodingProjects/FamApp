"""Files shared with the rest of the repo. In the image they sit next to backend/ (Dockerfile)."""

from __future__ import annotations

import os
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("FAMAPP_REPO_ROOT") or BACKEND.parent)
STRINGS = REPO / "shared/strings/de.json"
BRANDING = REPO / "branding.json"
APP_VERSION = REPO / "app/version.json"
