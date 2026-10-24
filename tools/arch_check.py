"""Architecture checks (AGENTS.md section 5, BUILDPLAN 1.2.7).

- Raw SQL only in backend/app/db/dialects/ (A7).
- No direct clock calls in logic code: backend and engine get the time from the time provider.
  Files named clock.py / *Clock.kt (the provider itself) are exempt.
- No DB access from JS: the UI reaches data only through app/data/repo*.ts; only those files
  may import the engine module.

Test files are exempt. One-line escape: a comment containing `arch-ignore: <reason>`.

    python tools/arch_check.py
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE_MARKER = "arch-ignore:"
SKIP_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "build",
    "dist",
    ".expo",
    "android",
    "__pycache__",
    "tests",
    "test",
    "__tests__",
    "androidTest",
}
SKIP_FILE = re.compile(r"(\.test\.|\.spec\.|^test_.*\.py$|_test\.py$|^conftest\.py$|Test\.kt$)")

SQL_WORDS = r"(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|PRAGMA|WITH|LOCK|REPLACE|TRUNCATE)\b"
RAW_SQL = [
    re.compile(r"\btext\(\s*[rRbBuUfF]{0,2}[\"']"),
    re.compile(r"\bexec_driver_sql\("),
    re.compile(r"\.execute\(\s*[rRbBuUfF]{0,2}[\"']{1,3}\s*" + SQL_WORDS, re.IGNORECASE),
]
PY_CLOCK = re.compile(
    r"\b(datetime\.(now|utcnow|today)|date\.today|time\.(time|time_ns|localtime|gmtime)|"
    r"datetime\.datetime\.(now|utcnow|today)|datetime\.date\.today)\s*\("
)
KT_CLOCK = re.compile(
    r"\b(System\.currentTimeMillis|System\.nanoTime|(Instant|LocalDateTime|LocalDate|LocalTime|ZonedDateTime|"
    r"OffsetDateTime|Clock\.System)\.now|Clock\.(systemUTC|systemDefaultZone)|SystemClock\.(elapsedRealtime|"
    r"uptimeMillis|currentThreadTimeMillis)|Calendar\.getInstance|Date)\s*\("
)
JS_DB = re.compile(
    r"""(from\s+|require\(\s*|import\(\s*)["'](expo-sqlite|react-native-sqlite[\w-]*|@op-engineering/op-sqlite|"""
    r"""@nozbe/watermelondb|realm|@realm/[\w-]+|react-native-mmkv|@react-native-async-storage/async-storage)["'/]"""
)
JS_ENGINE = re.compile(r"""(from\s+|require\(\s*|import\(\s*)["'][^"']*famapp-engine[^"']*["']""")


@dataclass(frozen=True)
class Rule:
    name: str
    roots: tuple[str, ...]
    suffixes: tuple[str, ...]
    patterns: tuple[re.Pattern, ...]
    message: str
    exempt: re.Pattern | None = None


RULES = (
    Rule(
        "raw-sql",
        ("backend", "dev"),
        (".py",),
        tuple(RAW_SQL),
        "raw SQL outside backend/app/db/dialects/ (use SQLAlchemy, A7)",
        re.compile(r"^backend/app/db/dialects/"),
    ),
    Rule(
        "clock",
        ("backend/app",),
        (".py",),
        (PY_CLOCK,),
        "direct clock call in logic code (use the time provider)",
        re.compile(r"(^|/)clock\.py$"),
    ),
    Rule(
        "clock",
        ("app/modules/famapp-engine",),
        (".kt", ".kts"),
        (KT_CLOCK,),
        "direct clock call in engine code (use the time provider)",
        re.compile(r"Clock[A-Za-z]*\.kt$"),
    ),
    Rule(
        "js-db",
        ("app",),
        (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"),
        (JS_DB,),
        "direct DB/storage access from JS (go through app/data/repo.ts)",
    ),
    Rule(
        "js-engine",
        ("app",),
        (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"),
        (JS_ENGINE,),
        "engine module imported outside app/data/repo*.ts",
        re.compile(r"^app/(data/repo[\w.]*\.(ts|tsx)$|modules/famapp-engine/)"),
    ),
)


def iter_files(root: Path, rule: Rule):
    for top in rule.roots:
        base = root / top
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            rel = path.relative_to(root)
            if not path.is_file() or path.suffix not in rule.suffixes:
                continue
            if any(part in SKIP_DIRS for part in rel.parts[:-1]) or SKIP_FILE.search(path.name):
                continue
            if rule.exempt and rule.exempt.search(rel.as_posix()):
                continue
            yield path, rel


def _code_only(line: str, suffix: str) -> str:
    """Drop a trailing line comment so commented-out calls do not count (good enough for one line)."""
    stripped = line.lstrip()
    if suffix == ".py":
        return "" if stripped.startswith("#") else line
    return "" if stripped.startswith(("//", "*", "/*")) else line


def run(root: Path) -> list[str]:
    errors = []
    for rule in RULES:
        for path, rel in iter_files(root, rule):
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if IGNORE_MARKER in line:
                    continue
                code = _code_only(line, path.suffix)
                if any(p.search(code) for p in rule.patterns):
                    errors.append(f"{rel.as_posix()}:{number}: [{rule.name}] {rule.message}: {line.strip()[:80]}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="architecture checks")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    errors = run(args.root)
    for error in errors:
        print(f"arch: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
