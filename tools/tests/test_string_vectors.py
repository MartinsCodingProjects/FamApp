"""Checks shared/test-vectors/strings/ against a minimal reference t().

The real helpers live in backend (1.4), app (1.5) and engine-core (2.2) and run the same vectors.
"""

import json
import re

import pytest

import strings_check
from conftest import REPO

VECTORS = json.loads((REPO / "shared/test-vectors/strings/t.json").read_text(encoding="utf-8"))


def reference_t(strings: dict, key: str, params: dict) -> str:
    value = strings.get(key)
    if value is None:
        return key
    if isinstance(value, dict):
        count = params.get("count")
        form = "one" if isinstance(count, int) and not isinstance(count, bool) and count == 1 else "other"
        value = value.get(form, value["other"])

    def substitute(match: re.Match) -> str:
        name = match.group(1)
        return str(params[name]) if name in params else match.group(0)

    return strings_check.PLACEHOLDER.sub(substitute, value)


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: c["name"])
def test_vector(case):
    assert reference_t(VECTORS["strings"], case["key"], case["params"]) == case["expected"]


def test_vector_strings_table_is_valid():
    report = strings_check.Report()
    strings_check.check_strings_file(VECTORS["strings"], report)
    assert report.errors == []
