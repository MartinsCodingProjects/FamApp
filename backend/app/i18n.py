"""t(key, params) over shared/strings/de.json (README 8.4).

Behavior is fixed by shared/test-vectors/strings/: unknown key → the key; missing parameter →
`{name}` stays; plural form `one` only for integer count == 1, otherwise `other`.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.paths import STRINGS

PLACEHOLDER = re.compile(r"\{([a-z][a-zA-Z0-9]*)\}")
Strings = dict[str, str | dict[str, str]]


@lru_cache
def load_strings(path: Path = STRINGS) -> Strings:
    return json.loads(path.read_text(encoding="utf-8"))


def plural_form(count: object) -> str:
    # German (CLDR): "one" for exactly 1, everything else "other".
    return "one" if isinstance(count, int) and not isinstance(count, bool) and count == 1 else "other"


def render(strings: Strings, key: str, params: dict[str, object] | None = None) -> str:
    params = params or {}
    value = strings.get(key)
    if value is None:
        return key
    if isinstance(value, dict):
        value = value.get(plural_form(params.get("count")), value["other"])

    def substitute(match: re.Match) -> str:
        name = match.group(1)
        return str(params[name]) if name in params else match.group(0)

    return PLACEHOLDER.sub(substitute, value)


def t(key: str, params: dict[str, object] | None = None, **kwargs: object) -> str:
    return render(load_strings(), key, {**(params or {}), **kwargs})
