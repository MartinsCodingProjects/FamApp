from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import SyncedMixin
from app.db.types import UTCDateTime

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def default_quiet_hours() -> dict:
    # README 3.2 / decisions section 12: 22:00-06:00 every day; crossing midnight belongs to the start day.
    return {day: {"start": "22:00", "end": "06:00"} for day in WEEKDAYS}


class User(SyncedMixin, Base):
    __tablename__ = "users"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")  # 'admin' | 'user'
    time_zone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Berlin")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)


class UserSettings(SyncedMixin, Base):
    """Per-user settings (decisions section 12); 3.2 adds the remaining intervals."""

    __tablename__ = "user_settings"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, unique=True)
    quiet_hours: Mapped[dict] = mapped_column(JSON, nullable=False, default=default_quiet_hours)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="remind")  # remind | essentials | dnd
    mode_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    mode_schedule: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    theme: Mapped[str] = mapped_column(String(10), nullable=False, default="system")  # system | light | dark
