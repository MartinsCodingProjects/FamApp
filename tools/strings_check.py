"""UI string checks (README 8.4, shared/strings/README.md).

Errors (exit 1):
- shared/strings/de.json is malformed (key format, value shape, plural forms, placeholders)
- code calls t("key") with a key that does not exist
- code passes a literal parameter set that does not match the text's placeholders
- German string literals in code

Warnings: keys that no code mentions (unused).

    python tools/strings_check.py
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRINGS = Path("shared/strings/de.json")
SCAN_DIRS = ("app", "backend", "dev")
CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".kt", ".kts"}
TEMPLATE_EXT = {".html", ".jinja", ".j2"}
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
    "test-vectors",
    "fixtures",
}
SKIP_FILE = re.compile(r"(\.generated\.|\.test\.|\.spec\.|^test_.*\.py$|_test\.py$|Test\.kt$)")
IGNORE_MARKER = "i18n-ignore"

KEY = re.compile(r"^[a-z][a-zA-Z0-9]*(\.[a-z][a-zA-Z0-9]*)+$")
PLACEHOLDER = re.compile(r"\{([a-z][a-zA-Z0-9]*)\}")
PLURAL_FORMS = {"zero", "one", "two", "few", "many", "other"}
KEY_LITERAL = re.compile(r"""["'`]([a-z][a-zA-Z0-9]*(?:\.[a-z][a-zA-Z0-9]*)+)["'`]""")
T_CALL = re.compile(r"""(?<![\w.$])t\(\s*(["'`])([^"'`\\\n]*)\1""")
STRING_LITERAL = re.compile(r""""(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`""")
UMLAUT = re.compile(r"[äöüÄÖÜß]")
# Common German words that rarely occur in English code; whole words, case-insensitive.
GERMAN_WORDS = re.compile(
    r"\b(und|nicht|oder|bitte|keine?|noch|wird|wurde|sind|heute|morgen|gestern|weiter|"
    r"abbrechen|speichern|erledigt|einstellungen|erinnerung|benachrichtigung|ruhezeit|"
    r"zugestellt|gesendet|anmelden|abmelden|passwort|termin|aufgabe|mach ich)\b",
    re.IGNORECASE,
)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def placeholders(value: str | dict) -> set[str]:
    texts = value.values() if isinstance(value, dict) else [value]
    return {name for text in texts for name in PLACEHOLDER.findall(text)}


def check_strings_file(strings: dict, report: Report) -> None:
    keys = list(strings)
    if keys != sorted(keys):
        report.errors.append(f"{STRINGS}: keys must be sorted alphabetically")
    for key, value in strings.items():
        where = f"{STRINGS}: {key}"
        if not KEY.match(key):
            report.errors.append(f"{where}: key must be dotted lowerCamelCase segments by area (e.g. todo.action.done)")
        if isinstance(value, str):
            if not value.strip():
                report.errors.append(f"{where}: empty text")
            continue
        if not isinstance(value, dict):
            report.errors.append(f"{where}: value must be a string or a plural object")
            continue
        unknown = set(value) - PLURAL_FORMS
        if unknown:
            report.errors.append(f"{where}: unknown plural forms {sorted(unknown)}")
        if "other" not in value:
            report.errors.append(f"{where}: plural object needs an 'other' form")
        if not all(isinstance(text, str) and text.strip() for text in value.values()):
            report.errors.append(f"{where}: every plural form must be a non-empty string")
            continue
        # A form may leave out {count} ("Ein Todo"); all other placeholders must match.
        sets = {form: set(PLACEHOLDER.findall(text)) - {"count"} for form, text in value.items()}
        if len({frozenset(s) for s in sets.values()}) > 1:
            detail = ", ".join(f"{form}: {sorted(s)}" for form, s in sets.items())
            report.errors.append(f"{where}: placeholder mismatch between plural forms ({detail})")
        if "count" not in PLACEHOLDER.findall(value.get("other", "")):
            report.errors.append(f"{where}: the 'other' form of a plural key must use {{count}}")


def _balanced(text: str, start: int, open_char: str, close_char: str) -> str | None:
    """Return the content between text[start] == open_char and its matching close_char."""
    depth = 0
    quote = None
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in "\"'`":
            quote = ch
        elif ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    return None


def _split_top_level(text: str) -> list[str]:
    items, depth, current, quote, escaped = [], 0, [], None, False
    for ch in text:
        if quote:
            current.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in "\"'`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if "".join(current).strip():
        items.append("".join(current).strip())
    return items


def call_params(source: str, call_start: int) -> set[str] | None:
    """Parameter names of the t() call starting at call_start; set() for none, None if not static."""
    inner = _balanced(source, source.index("(", call_start), "(", ")")
    if inner is None:
        return None
    args = _split_top_level(inner)
    if len(args) == 1:
        return set()
    rest = args[1:]
    first = rest[0]
    if first.startswith("{") and len(rest) == 1:  # TS object or Python dict literal
        items = _split_top_level(first[1:-1])
        pattern = r"""^["']?([A-Za-z_]\w*)["']?\s*(:|$)"""
    elif first.startswith("mapOf(") and len(rest) == 1:  # Kotlin
        items = _split_top_level(first[len("mapOf(") : -1])
        pattern = r"""^"([A-Za-z_]\w*)"\s+to\s"""
    elif all(re.match(r"^[A-Za-z_]\w*\s*=(?!=)", arg) for arg in rest):  # Python keyword arguments
        items = rest
        pattern = r"^([A-Za-z_]\w*)\s*="
    else:
        return None
    names = set()
    for item in items:
        match = re.match(pattern, item)
        if not match or item.startswith("..."):
            return None
        names.add(match.group(1))
    return names


def iter_files(root: Path):
    for top in SCAN_DIRS:
        base = root / top
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            rel = path.relative_to(root)
            if not path.is_file() or any(part in SKIP_DIRS for part in rel.parts[:-1]):
                continue
            if SKIP_FILE.search(path.name):
                continue
            if path.suffix in CODE_EXT or path.suffix in TEMPLATE_EXT:
                yield path, rel


def python_literals(source: str):
    """(line, text) for every string literal in Python source, comments excluded."""
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.STRING:
                yield tok.start[0], tok.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        yield from regex_literals(source)


def regex_literals(source: str):
    in_block = False
    for number, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if in_block:
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith("/*"):
            in_block = "*/" not in stripped
            continue
        if stripped.startswith(("//", "*", "#")):
            continue
        code = re.split(r"\s//\s", line, maxsplit=1)[0]
        for match in STRING_LITERAL.finditer(code):
            yield number, match.group(0)


def template_texts(source: str):
    for number, line in enumerate(source.splitlines(), 1):
        text = re.sub(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}|<[^>]*>", " ", line)
        yield number, text


def is_german(text: str) -> bool:
    return bool(UMLAUT.search(text) or GERMAN_WORDS.search(text))


def check_code(root: Path, strings: dict, report: Report) -> set[str]:
    mentioned: set[str] = set()
    for path, rel in iter_files(root):
        source = path.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()

        def ignored(line_number: int, lines: list[str] = lines) -> bool:
            return 0 < line_number <= len(lines) and IGNORE_MARKER in lines[line_number - 1]

        mentioned.update(KEY_LITERAL.findall(source))
        if path.suffix in TEMPLATE_EXT:
            literals = template_texts(source)
        elif path.suffix == ".py":
            literals = python_literals(source)
        else:
            literals = regex_literals(source)
        for line_number, text in literals:
            if is_german(text) and not ignored(line_number):
                snippet = text.strip()[:60]
                report.errors.append(f"{rel}:{line_number}: German text in code, use a key from {STRINGS}: {snippet}")

        for match in T_CALL.finditer(source):
            key = match.group(2)
            line_number = source.count("\n", 0, match.start()) + 1
            if ignored(line_number):
                continue
            where = f"{rel}:{line_number}"
            if key not in strings:
                report.errors.append(f"{where}: unknown string key {key!r}")
                continue
            passed = call_params(source, match.start())
            if passed is None:
                continue
            expected = placeholders(strings[key])
            if passed != expected:
                report.errors.append(
                    f"{where}: placeholder mismatch for {key!r}: "
                    f"text uses {sorted(expected)}, call passes {sorted(passed)}"
                )
    return mentioned


def run(root: Path) -> Report:
    report = Report()
    try:
        strings = json.loads((root / STRINGS).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(f"{STRINGS}: cannot read: {exc}")
        return report
    if not isinstance(strings, dict):
        report.errors.append(f"{STRINGS}: must be a JSON object")
        return report
    check_strings_file(strings, report)
    mentioned = check_code(root, strings, report)
    for key in strings:
        if key not in mentioned:
            report.warnings.append(f"{STRINGS}: {key}: not used in code yet")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UI string checks")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--verbose", action="store_true", help="list every warning")
    args = parser.parse_args(argv)
    report = run(args.root)
    if args.verbose:
        for warning in report.warnings:
            print(f"strings: warning: {warning}", file=sys.stderr)
    elif report.warnings:
        print(f"strings: {len(report.warnings)} warning(s), e.g. unused keys (--verbose lists them)", file=sys.stderr)
    for error in report.errors:
        print(f"strings: {error}", file=sys.stderr)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
