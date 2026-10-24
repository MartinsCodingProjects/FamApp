from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import LocalMixin, SyncedMixin
from app.db.types import UTCDateTime


class Notification(SyncedMixin, Base):
    """Server-created notification (activity, explicit urgent, system, test). Carries a string key
    plus parameters, never finished text (README 8.4). Display key `notif:<id>` (README 3.5)."""

    __tablename__ = "notifications"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # activity | urgent | system | test
    message_key: Mapped[str] = mapped_column(String(100), nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    todo_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)  # FK once todos exist (Run 3)
    show_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Delivery(LocalMixin, Base):
    """Display key x device (README 3.7). Key includes the planned minute for device-planned displays."""

    __tablename__ = "deliveries"
    __table_args__ = (UniqueConstraint("display_key", "device_id"),)
    display_key: Mapped[str] = mapped_column(String(255), nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("devices.id"), nullable=False, index=True)
    planned_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    shown_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    acked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AlarmFiring(LocalMixin, Base):
    """One alarm firing reported by a device (decisions section 11). Device → server only."""

    __tablename__ = "alarm_firings"
    device_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("devices.id"), nullable=False, index=True)
    planned_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    fired_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    alarm_type: Mapped[str] = mapped_column(String(20), nullable=False)  # alarm_clock | exact_idle
    idle: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sync_result: Mapped[str] = mapped_column(String(20), nullable=False)  # ok | timeout | error | no_network
    sync_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
