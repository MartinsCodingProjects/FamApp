from datetime import date

import npm_audit_gate as g

REPORT = {
    "vulnerabilities": {
        "zod": {"via": [{"url": "https://github.com/advisories/GHSA-mrhx-c7xc-m3w5", "severity": "high"}]},
        "@expo/cli": {"via": ["zod"]},
        "left-pad": {"via": [{"url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc", "severity": "moderate"}]},
    }
}


def test_unlisted_high_fails():
    assert g.gate(REPORT, {}, date(2026, 10, 24)) == ["high advisory GHSA-mrhx-c7xc-m3w5 in zod"]


def test_listed_high_passes_until_it_expires():
    allow = {"GHSA-mrhx-c7xc-m3w5": date(2027, 1, 24)}
    assert g.gate(REPORT, allow, date(2026, 10, 24)) == []
    problems = g.gate(REPORT, allow, date(2027, 1, 25))
    assert any("expired" in p for p in problems) and any("GHSA-mrhx" in p and "zod" in p for p in problems)


def test_moderate_never_fails():
    assert g.gate({"vulnerabilities": {"x": REPORT["vulnerabilities"]["left-pad"]}}, {}, date(2026, 1, 1)) == []


def test_repo_allowlist_parses():
    from conftest import REPO

    entries = g.read_allowlist(REPO / "tools/audit-allowlist.txt")
    assert entries and all(isinstance(d, date) for d in entries.values())
