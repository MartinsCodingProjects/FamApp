"""docs/spec-sync.md covers what BUILDPLAN 1.6 requires (doc test, 1.6.7)."""

import re

import pytest

from conftest import REPO

SPEC = (REPO / "docs/spec-sync.md").read_text(encoding="utf-8")
HEADINGS = re.findall(r"^#{2,3} (.+)$", SPEC, flags=re.MULTILINE)

REQUIRED_SECTIONS = [
    "1. Endpoints",
    "2. Delta",
    "3. Operations",
    "4. Conflicts",
    "5. Error cases",
    "6. Versions",
    "7. Test scenarios",
]
REQUIRED_TERMS = [
    "GET /api/sync",
    "POST /api/sync/push",
    "POST /api/devices/me/fcm-token",
    "X-Famapp-Protocol",
    "X-Famapp-App-Version",
    "server_time",
    "min_app_version",
    "latest_app_version",
    "worker_heartbeat_age_s",
    "next_since",
    "has_more",
    "Tombstones",
    "op_id",
    "processed_ops",
    "last-write-wins",
    "Deletion wins",
    "Clock skew",
    "Tie",
    "conflict_log",
    "rejected",
    "retry",
    "app_too_old",
    "unsupported_protocol",
    "token_expired",
    "device_locked",
    "Unknown fields and tables are ignored",
]
REQUIRED_OPS = [
    "todo.create",
    "todo.update_content",
    "todo.set_status",
    "todo.delete",
    "ack",
    "snooze",
    "claim",
    "device_status",
    "alarm_firing",
]


@pytest.mark.parametrize("section", REQUIRED_SECTIONS)
def test_required_sections(section):
    assert section in HEADINGS


@pytest.mark.parametrize("term", REQUIRED_TERMS)
def test_required_terms(term):
    assert term in SPEC


@pytest.mark.parametrize("op", REQUIRED_OPS)
def test_every_operation_has_a_table_row(op):
    assert re.search(rf"^\| `{re.escape(op)}` \|", SPEC, flags=re.MULTILINE)


def test_scenario_ids_are_unique_and_sequential():
    ids = re.findall(r"^\| (S\d{2}) \|", SPEC, flags=re.MULTILINE)
    assert ids == [f"S{n:02d}" for n in range(1, len(ids) + 1)] and len(ids) >= 20
