import json
from pathlib import Path

import strings_check
from conftest import REPO


def write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def set_strings(root: Path, strings: dict) -> None:
    write(root, str(strings_check.STRINGS), json.dumps(strings))


def errors(root: Path) -> list[str]:
    return strings_check.run(root).errors


def test_repo_passes():
    assert strings_check.main(["--root", str(REPO)]) == 0


def test_valid_usage_in_all_languages_passes(repo_copy):
    write(repo_copy, "app/screens/Todo.tsx", 'const a = t("todo.delivery.delivered", { time });\n')
    write(repo_copy, "backend/app/domain/x.py", 'text = t("sync.banner.pending", count=n)\n')
    write(repo_copy, "backend/app/domain/y.py", 'text = t("mode.dnd.until", {"time": until})\n')
    write(
        repo_copy,
        "app/modules/famapp-engine/engine-core/src/A.kt",
        't("todo.marker.notSentUrgent", mapOf("name" to n))\n',
    )
    write(repo_copy, "backend/app/admin/templates/a.html", "<button>{{ t('todo.action.claim') }}</button>\n")
    write(repo_copy, "app/x.ts", "t(key, params);\nt('todo.snooze.untilTomorrow', params);\n")
    assert errors(repo_copy) == []


def test_unknown_key_fails(repo_copy):
    write(repo_copy, "app/screens/Todo.tsx", 'label = t("todo.action.dnoe");\n')
    assert any(
        "unknown string key 'todo.action.dnoe'" in e and "app/screens/Todo.tsx:1" in e for e in errors(repo_copy)
    )
    assert strings_check.main(["--root", str(repo_copy)]) == 1


def test_broken_key_name_in_strings_file_fails(repo_copy):
    strings = json.loads((REPO / strings_check.STRINGS).read_text(encoding="utf-8"))
    strings["Todo.Action-Done"] = "Erledigt"
    set_strings(repo_copy, dict(sorted(strings.items())))
    assert any("Todo.Action-Done" in e and "dotted lowerCamelCase" in e for e in errors(repo_copy))


def test_unsorted_or_invalid_json_fails(repo_copy):
    set_strings(repo_copy, {"b.key": "x", "a.key": "y"})
    assert any("sorted" in e for e in errors(repo_copy))
    write(repo_copy, str(strings_check.STRINGS), "{ not json")
    assert any("cannot read" in e for e in errors(repo_copy))


def test_placeholder_mismatch_fails(repo_copy):
    write(repo_copy, "app/a.ts", 't("todo.delivery.delivered", { when: x });\n')
    write(repo_copy, "backend/app/b.py", 't("mode.dnd.until")\n')
    write(repo_copy, "app/c.kt", 't("sync.banner.pending", mapOf("n" to 3))\n')
    write(repo_copy, "backend/app/d.py", 't("notification.overdue.title", count=3)\n')
    found = errors(repo_copy)
    assert any("app/a.ts:1: placeholder mismatch" in e and "['time']" in e and "['when']" in e for e in found)
    assert any("backend/app/b.py:1: placeholder mismatch" in e for e in found)
    assert any("app/c.kt:1: placeholder mismatch" in e for e in found)
    assert any("backend/app/d.py:1: placeholder mismatch" in e and "['count', 'titles']" in e for e in found)


def test_plural_rules_in_strings_file(repo_copy):
    set_strings(
        repo_copy,
        {
            "a.noOther": {"one": "{count} Ding"},
            "b.formsDiffer": {"one": "{count} Ding für {name}", "other": "{count} Dinge"},
            "c.noCount": {"one": "Ein Ding", "other": "Viele Dinge"},
            "d.badForm": {"single": "x", "other": "{count} x"},
            "e.oneWithoutCount": {"one": "Ein Ding", "other": "{count} Dinge"},
        },
    )
    found = errors(repo_copy)
    assert any("a.noOther" in e and "'other'" in e for e in found)
    assert any("b.formsDiffer" in e and "placeholder mismatch" in e for e in found)
    assert any("c.noCount" in e and "{count}" in e for e in found)
    assert any("d.badForm" in e and "unknown plural forms" in e for e in found)
    assert not any("e.oneWithoutCount" in e for e in found)


def test_german_literals_fail(repo_copy):
    write(repo_copy, "app/screens/A.tsx", 'const label = "Später";\n')
    write(repo_copy, "backend/app/b.py", 'msg = "Server nicht erreichbar"\n# a comment: nicht erreichbar\n')
    write(repo_copy, "app/c.kt", 'val s = "Mach ich"\n')
    write(repo_copy, "backend/app/admin/templates/t.html", "<p>Speichern</p>\n")
    found = errors(repo_copy)
    for where in ("app/screens/A.tsx:1", "backend/app/b.py:1", "app/c.kt:1", "backend/app/admin/templates/t.html:1"):
        assert any(where in e and "German text" in e for e in found), where
    assert not any("backend/app/b.py:2" in e for e in found)


def test_german_literal_exemptions(repo_copy):
    write(repo_copy, "app/a.ts", 'const x = "Später"; // i18n-ignore: brand name\n')
    write(repo_copy, "app/a.test.ts", 'expect(text).toBe("Mach ich");\n')
    write(repo_copy, "backend/tests/test_a.py", 'assert text == "Mach ich"\n')
    write(repo_copy, "app/b.ts", 'const english = "undo, or not";\n')
    assert errors(repo_copy) == []


def test_unused_keys_are_warnings_only(repo_copy):
    report = strings_check.run(repo_copy)
    assert report.errors == []
    assert any("todo.action.claim" in w for w in report.warnings)
    write(repo_copy, "backend/app/x.py", 'KEY = "todo.action.claim"\n')
    assert not any("todo.action.claim" in w for w in strings_check.run(repo_copy).warnings)
