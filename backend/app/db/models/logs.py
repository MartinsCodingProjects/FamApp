from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import LocalMixin
from app.db.types import UTCDateTime


class AuditLog(LocalMixin, Base):
    """Security events: logins, pairings, revocations, admin actions, secret changes (README 9)."""

    __tablename__ = "audit_log"
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    actor_device_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # never secrets or todo content


class ConflictLog(LocalMixin, Base):
    """Changes that lost last-write-wins (spec-sync.md section 4.5)."""

    __tablename__ = "conflict_log"
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String(60), nullable=False)
    row_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    field_group: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)  # older | tie | deleted
    losing_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    losing_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    losing_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    winning_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    winning_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    winning_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class JobLog(LocalMixin, Base):
    """Worker job runs (watchdog, series, calendar, heartbeat) for the admin UI."""

    __tablename__ = "job_log"
    job: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # running | ok | error
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
