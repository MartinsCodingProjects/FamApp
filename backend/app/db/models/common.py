from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime


class RevCounter(Base):
    """One row (id = 1) holding the last assigned rev; only next_rev() touches it."""

    __tablename__ = "rev_counter"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)


class SyncedMixin:
    """Common columns of every synced table (README 6). Timestamps come from the Clock via stamp()."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rev: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class LocalMixin:
    """Columns of server-only tables (never synced)."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
