"""Invariants of the CI setup (BUILDPLAN 1.2.1, 1.2.9, 1.2.12)."""

import subprocess

import pytest
import yaml
from conftest import REPO

WORKFLOWS = REPO / ".github/workflows"


def areas(paths: list[str] | None) -> dict[str, str]:
    args = [str(REPO / "tools/ci-changes.sh")] + (["--all"] if paths is None else [])
    out = subprocess.run(args, input="\n".join(paths or []), capture_output=True, text=True, check=True).stdout
    return dict(line.split("=", 1) for line in out.splitlines())


def changed(paths: list[str] | None) -> set[str]:
    result = areas(paths)
    return {k for k in ("backend", "app", "shared", "tools", "docs") if result[k] == "true"}


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["BUILDPLAN.md", "docs/decisions.md"], {"docs"}),
        (["backend/app/main.py", "deploy/docker-compose.yml"], {"backend"}),
        (["app/screens/Todos.tsx", "branding.json"], {"app"}),
        (["shared/strings/de.json"], {"shared"}),
        (["tools/tokens.py", "Makefile", "package-lock.json"], {"tools"}),
        (["backend/README.md"], {"backend"}),
        ([".github/workflows/ci.yml"], {"backend", "app", "shared", "tools", "docs"}),
        ([], set()),
        (None, {"backend", "app", "shared", "tools", "docs"}),
    ],
)
def test_change_detection(paths, expected):
    assert changed(paths) == expected


def test_project_flags_present():
    result = areas([])
    assert result["has_backend"] in ("true", "false") and result["has_app"] in ("true", "false")


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def test_ci_gate_needs_every_job_and_always_runs():
    ci = load("ci.yml")
    jobs = ci["jobs"]
    gate = jobs["ci-gate"]
    assert gate["if"] == "always()"
    assert set(gate["needs"]) == set(jobs) - {"ci-gate"}


def test_no_workflow_level_path_filters():
    ci = load("ci.yml")
    triggers = ci[True]  # PyYAML reads the key `on` as boolean True
    for event in ("pull_request", "push"):
        config = triggers.get(event) or {}
        assert "paths" not in config and "paths-ignore" not in config


def test_signing_secrets_only_in_release_workflow():
    for path in WORKFLOWS.glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        if path.name == "release.yml":
            continue
        assert "ANDROID_KEY" not in text and "environment:" not in text, path.name


def test_release_workflow_runs_only_on_push_to_release():
    release = load("release.yml")
    assert release[True] == {"push": {"branches": ["release"]}}
    assert release["jobs"]["apk"]["environment"] == "release"
