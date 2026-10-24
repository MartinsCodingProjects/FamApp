from __future__ import annotations

from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import LocalMixin


class Secret(LocalMixin, Base):
    """Encrypted configuration value (README 9; format in app/security/crypto.py, 1.8)."""

    __tablename__ = "secrets"
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
