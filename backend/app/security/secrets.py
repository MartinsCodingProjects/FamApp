"""Secret store on the `secrets` table (BUILDPLAN 1.8.2).

Values come back as SecretStr, so they never end up in logs, reprs or templates by accident.
Every change writes an audit log entry with the secret's name only.
"""

from __future__ import annotations

import re
import uuid

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import Clock
from app.db.models import AuditLog, Secret
from app.security import crypto

NAME = re.compile(r"^[a-z][a-z0-9_.]{0,99}$")


class SecretStore:
    def __init__(self, session: Session, master_key: bytes, clock: Clock) -> None:
        if not master_key:
            raise ValueError("MASTER_KEY is not set")
        self.session = session
        self.key = master_key
        self.clock = clock

    @staticmethod
    def _check(name: str) -> None:
        if not NAME.match(name):
            raise ValueError(f"invalid secret name {name!r}")

    def _row(self, name: str) -> Secret | None:
        return self.session.scalars(select(Secret).where(Secret.name == name)).one_or_none()

    def exists(self, name: str) -> bool:
        self._check(name)
        return self._row(name) is not None

    def get(self, name: str) -> SecretStr | None:
        self._check(name)
        row = self._row(name)
        if row is None:
            return None
        return SecretStr(crypto.decrypt(self.key, name, row.ciphertext).decode("utf-8"))

    def set(self, name: str, value: str | SecretStr, actor_user_id: uuid.UUID | None = None) -> None:
        """Create or replace a secret (caller commits)."""
        self._check(name)
        plain = value.get_secret_value() if isinstance(value, SecretStr) else value
        now = self.clock.now()
        row = self._row(name)
        created = row is None
        if row is None:
            row = Secret(name=name, created_at=now)
            self.session.add(row)
        row.ciphertext = crypto.encrypt(self.key, name, plain.encode("utf-8"))
        row.updated_at = now
        self.session.add(
            AuditLog(
                at=now,
                created_at=now,
                updated_at=now,
                event="secret.created" if created else "secret.changed",
                actor_user_id=actor_user_id,
                details={"name": name},
            )
        )
