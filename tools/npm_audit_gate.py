"""Fails on high/critical npm advisories that are not in the dated allowlist (tools/audit.sh).

python tools/npm_audit_gate.py <npm audit --json output> <allowlist> [--today YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

FAILING = {"high", "critical"}
GHSA = re.compile(r"GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}")


def read_allowlist(path: Path) -> dict[str, date]:
    entries = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 3 or not GHSA.fullmatch(parts[0]):
            raise ValueError(f"{path}:{number}: expected '<GHSA id> <YYYY-MM-DD> <reason>'")
        entries[parts[0]] = date.fromisoformat(parts[1])
    return entries


def advisories(report: dict) -> dict[str, tuple[str, str]]:
    """GHSA id → (severity, package) for every advisory in an `npm audit --json` report."""
    found = {}
    for name, vuln in report.get("vulnerabilities", {}).items():
        for via in vuln.get("via", []):
            if isinstance(via, dict):
                match = GHSA.search(via.get("url", ""))
                key = match.group(0) if match else str(via.get("source"))
                found[key] = (via.get("severity", "unknown"), name)
    return found


def gate(report: dict, allowlist: dict[str, date], today: date) -> list[str]:
    problems = []
    for ghsa, expires in allowlist.items():
        if expires < today:
            problems.append(f"allowlist entry {ghsa} expired on {expires}: review it")
    for ghsa, (severity, package) in sorted(advisories(report).items()):
        if severity in FAILING and (ghsa not in allowlist or allowlist[ghsa] < today):
            problems.append(f"{severity} advisory {ghsa} in {package}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("allowlist", type=Path)
    parser.add_argument("--today", type=date.fromisoformat, default=None)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8") or "{}")
    problems = gate(report, read_allowlist(args.allowlist), args.today or date.today())
    for problem in problems:
        print(f"npm audit: {problem}", file=sys.stderr)
    if not problems:
        print("npm audit: no unaccepted high/critical advisories")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
