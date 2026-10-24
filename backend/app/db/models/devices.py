from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import LocalMixin
from app.db.types import UTCDateTime


class Device(LocalMixin, Base):
    """A paired phone (README 6). Not synced."""

    __tablename__ = "devices"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    app_version: Mapped[int | None] = mapped_column(Integer, nullable=True)  # versionCode
    fcm_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    fcm_token_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    device_status: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # permission, channel importance
    locked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    locked_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)


class DeviceToken(LocalMixin, Base):
    """Refresh token hashes; a chain per device for the generous reuse rule (decisions section 3, 1.10)."""

    __tablename__ = "device_tokens"
    device_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("devices.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    predecessor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("device_tokens.id"), nullable=True)
    first_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
