from __future__ import annotations

import json
from functools import lru_cache

from app.paths import APP_VERSION, BRANDING


@lru_cache
def branding() -> dict:
    return json.loads(BRANDING.read_text(encoding="utf-8"))


@lru_cache
def app_version() -> dict:
    """Latest app version (README 7, 10): versionName and versionCode from app/version.json."""
    return json.loads(APP_VERSION.read_text(encoding="utf-8"))
