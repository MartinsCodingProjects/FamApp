import json
from pathlib import Path

import pytest

import tokens
from conftest import REPO


def run(root: Path, *args: str) -> int:
    return tokens.main(["--root", str(root), *args])


def edit_tokens(root: Path, change) -> None:
    path = root / tokens.SOURCE
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_committed_generated_files_are_up_to_date():
    assert run(REPO, "--check") == 0


def test_generate_then_check_passes(repo_copy):
    assert run(repo_copy, "--check") == 1  # nothing generated yet
    assert run(repo_copy) == 0
    assert run(repo_copy, "--check") == 0
    for rel in tokens.outputs(repo_copy):
        assert (repo_copy / rel).read_text(encoding="utf-8").startswith(("//", "/*", "<?xml"))


def test_hand_edited_generated_file_fails_check(repo_copy):
    run(repo_copy)
    css = repo_copy / tokens.CSS_OUT
    css.write_text(css.read_text(encoding="utf-8").replace("#dc2626", "#ff0000"), encoding="utf-8")
    assert run(repo_copy, "--check") == 1


def test_changed_source_makes_generated_files_stale(repo_copy, capsys):
    run(repo_copy)
    edit_tokens(repo_copy, lambda d: d["semantic"]["color"]["state"]["urgent"].update(light="{color.red.700}"))
    assert run(repo_copy, "--check") == 1
    assert "stale" in capsys.readouterr().err


def test_output_formats(repo_copy):
    run(repo_copy)
    ts = (repo_copy / tokens.TS_OUT).read_text(encoding="utf-8")
    assert 'urgent: "#dc2626"' in ts and "export const darkColors: ColorTokens" in ts
    assert "card: 12," in ts  # radius.card -> radius.lg
    css = (repo_copy / tokens.CSS_OUT).read_text(encoding="utf-8")
    assert "--color-state-urgent: #dc2626;" in css and "--color-state-urgent: #f87171;" in css
    assert "--space-card-padding: 16px;" in css and "--duration-press: 120ms;" in css
    assert '[data-theme="dark"]' in css and "prefers-color-scheme: dark" in css
    light = (repo_copy / tokens.XML_LIGHT_OUT).read_text(encoding="utf-8")
    dark = (repo_copy / tokens.XML_DARK_OUT).read_text(encoding="utf-8")
    assert '<color name="color_state_due_soon">#d97706</color>' in light
    assert '<color name="color_state_due_soon">#fbbf24</color>' in dark


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda d: d["semantic"]["color"]["state"].update(urgent={"light": "#ff0000", "dark": "{color.red.400}"}),
            "must reference a base token",
        ),
        (lambda d: d["semantic"]["color"]["state"].update(urgent={"light": "{color.red.600}"}), "'light' and a 'dark'"),
        (
            lambda d: d["semantic"]["color"]["state"].update(
                urgent={"light": "{color.red.999}", "dark": "{color.red.4}"}
            ),
            "unknown base token",
        ),
        (lambda d: d["semantic"]["space"]["card"].update(padding="{radius.md}"), "must reference a space token"),
        (lambda d: d["base"]["color"]["red"].update({"600": "red"}), "lowercase #rrggbb"),
        (lambda d: d["base"]["space"].update({"4": "16px"}), "must be an integer"),
        (lambda d: d["semantic"].update(shadow={"card": "{space.1}"}), "unknown group"),
    ],
)
def test_invalid_tokens_fail(repo_copy, capsys, change, message):
    edit_tokens(repo_copy, change)
    assert run(repo_copy) == 1
    assert message in capsys.readouterr().err
