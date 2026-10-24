"""Delta by rev across all synced tables (spec-sync.md section 2)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Notification, User, UserSettings
from app.sync.protocol import iso

MAX_LIMIT = 1000
DEFAULT_LIMIT = 500


def plain(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return iso(value)
    return value


def fields(row, names: tuple[str, ...]) -> dict:
    return {name: plain(getattr(row, name)) for name in ("id", *names)}


@dataclass(frozen=True)
class SyncedTable:
    name: str
    model: type
    # (row, user_id) → data dict for this user, or None if the row is invisible to them
    project: Callable[[object, uuid.UUID], dict | None]


USER_FIELDS = ("name", "role", "time_zone", "created_at", "updated_at")
OTHER_USER_FIELDS = ("name",)
SETTINGS_FIELDS = ("user_id", "quiet_hours", "mode", "mode_until", "mode_schedule", "theme", "updated_at")
OTHER_SETTINGS_FIELDS = ("user_id", "mode", "mode_until", "mode_schedule")
NOTIFICATION_FIELDS = ("user_id", "kind", "message_key", "params", "todo_id", "show_at", "expires_at", "created_at")


def _users(row: User, me: uuid.UUID) -> dict:
    return fields(row, USER_FIELDS if row.id == me else OTHER_USER_FIELDS)


def _settings(row: UserSettings, me: uuid.UUID) -> dict:
    return fields(row, SETTINGS_FIELDS if row.user_id == me else OTHER_SETTINGS_FIELDS)


def _notifications(row: Notification, me: uuid.UUID) -> dict | None:
    return fields(row, NOTIFICATION_FIELDS) if row.user_id == me else None


# Later runs register their tables here (todos, series, people, categories, calendar …).
TABLES: tuple[SyncedTable, ...] = (
    SyncedTable("users", User, _users),
    SyncedTable("user_settings", UserSettings, _settings),
    SyncedTable("notifications", Notification, _notifications),
)


def delta(session: Session, user_id: uuid.UUID, since: int, limit: int, tables=TABLES) -> dict:
    # Examine the next `limit` rows by rev across all tables, visible or not, so invisible rows
    # still advance next_since (S03).
    candidates = []
    for table in tables:
        rows = session.scalars(
            select(table.model).where(table.model.rev > since).order_by(table.model.rev).limit(limit + 1)
        ).all()
        candidates.extend((row.rev, table, row) for row in rows)
    candidates.sort(key=lambda item: item[0])
    page, has_more = candidates[:limit], len(candidates) > limit
    changes = []
    for rev, table, row in page:
        data = table.project(row, user_id)
        if data is None:
            continue  # invisible to this user (also as a tombstone)
        if row.deleted_at is not None:
            changes.append(
                {
                    "table": table.name,
                    "id": str(row.id),
                    "rev": rev,
                    "deleted": True,
                    "data": {"deleted_at": iso(row.deleted_at)},
                }
            )
        else:
            changes.append({"table": table.name, "id": str(row.id), "rev": rev, "deleted": False, "data": data})
    next_since = page[-1][0] if page else since
    return {"changes": changes, "next_since": next_since, "has_more": has_more}
