from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime


class ProcessedOp(Base):
    """Push idempotency (spec-sync.md section 3): every applied op UUID with its stored result."""

    __tablename__ = "processed_ops"
    op_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    device_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("devices.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
