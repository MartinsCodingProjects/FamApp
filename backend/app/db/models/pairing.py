from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import LocalMixin
from app.db.types import UTCDateTime


class PairingCode(LocalMixin, Base):
    """One-time pairing code (spec-device-auth.md); only an HMAC of the code is stored."""

    __tablename__ = "pairing_codes"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    used_by_device_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_by_device_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)  # NULL = admin
