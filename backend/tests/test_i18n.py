import json

import pytest
from app.i18n import load_strings, render, t
from app.paths import REPO

VECTORS = json.loads((REPO / "shared/test-vectors/strings/t.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: c["name"])
def test_string_vectors(case):
    assert render(VECTORS["strings"], case["key"], case["params"]) == case["expected"]


def test_t_reads_de_json():
    assert "todo.action.claim" in load_strings()
    assert t("todo.action.claim") == "Mach ich"
    assert t("sync.banner.pending", count=1) == "1 Änderung noch nicht synchronisiert"
    assert t("sync.banner.pending", {"count": 3}) == "3 Änderungen noch nicht synchronisiert"
    assert t("does.not.exist") == "does.not.exist"
