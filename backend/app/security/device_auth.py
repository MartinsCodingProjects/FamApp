"""Pairing, access tokens and refresh rotation with the generous reuse rule (spec-device-auth.md)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import Clock
from app.db.models import AuditLog, Device, DeviceToken, PairingCode, User

ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
CODE_LENGTH = 8
CODE_TTL = timedelta(minutes=10)
ACCESS_TTL = timedelta(minutes=15)


class AuthError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code  # pairing_failed | invalid_token | token_expired | device_locked


def derive_key(master_key: bytes, purpose: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=purpose.encode()).derive(master_key)


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch not in " -\t")


def format_code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"


def _sha256(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


@dataclass
class Tokens:
    device_id: uuid.UUID
    user_id: uuid.UUID
    access_token: str
    access_expires_at: datetime
    refresh_token: str

    def as_json(self) -> dict:
        return {
            "device_id": str(self.device_id),
            "user_id": str(self.user_id),
            "access_token": self.access_token,
            "access_expires_at": self.access_expires_at.isoformat().replace("+00:00", "Z"),
            "refresh_token": self.refresh_token,
        }


class DeviceAuth:
    def __init__(self, session: Session, master_key: bytes, clock: Clock, ip: str | None = None) -> None:
        self.session = session
        self.clock = clock
        self.ip = ip
        self.code_key = derive_key(master_key, "famapp pairing code v1")
        self.access_key = derive_key(master_key, "famapp access token v1")

    # --- audit -----------------------------------------------------------------------------

    def audit(self, event: str, user_id=None, device_id=None, **details) -> None:
        now = self.clock.now()
        self.session.add(
            AuditLog(
                at=now,
                created_at=now,
                updated_at=now,
                event=event,
                actor_user_id=user_id,
                actor_device_id=device_id,
                ip=self.ip,
                details=details,
            )
        )

    # --- pairing codes ---------------------------------------------------------------------

    def _code_hash(self, code: str) -> str:
        return hmac.new(self.code_key, normalize_code(code).encode("ascii"), hashlib.sha256).hexdigest()

    def create_pairing_code(self, user: User, created_by_device: Device | None = None) -> tuple[str, datetime]:
        now = self.clock.now()
        code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        expires = now + CODE_TTL
        self.session.add(
            PairingCode(
                user_id=user.id,
                code_hash=self._code_hash(code),
                expires_at=expires,
                created_at=now,
                updated_at=now,
                created_by_device_id=created_by_device.id if created_by_device else None,
            )
        )
        self.audit("pairing_code.created", user.id, created_by_device.id if created_by_device else None)
        return format_code(code), expires

    def pair(self, code: str, device_name: str) -> Tokens:
        now = self.clock.now()
        row = self.session.scalars(
            select(PairingCode).where(PairingCode.code_hash == self._code_hash(code)).with_for_update()
        ).one_or_none()
        if row is None or row.used_at is not None or now >= row.expires_at:
            self.audit(
                "pairing.failed",
                row.user_id if row else None,
                reason="unknown" if row is None else ("used" if row.used_at else "expired"),
            )
            raise AuthError("pairing_failed")
        device = Device(user_id=row.user_id, name=device_name, created_at=now, updated_at=now)
        self.session.add(device)
        self.session.flush()
        row.used_at = now
        row.used_by_device_id = device.id
        row.updated_at = now
        self.audit("device.paired", row.user_id, device.id)
        return self._issue(device, predecessor=None)

    # --- tokens ----------------------------------------------------------------------------

    def _issue(self, device: Device, predecessor: DeviceToken | None) -> Tokens:
        now = self.clock.now()
        refresh = secrets.token_urlsafe(32)
        self.session.add(
            DeviceToken(
                device_id=device.id,
                token_hash=_sha256(refresh),
                created_at=now,
                updated_at=now,
                predecessor_id=predecessor.id if predecessor else None,
            )
        )
        expires = now + ACCESS_TTL
        access = jwt.encode(
            {
                "sub": str(device.id),
                "uid": str(device.user_id),
                "typ": "access",
                "iat": int(now.timestamp()),
                "exp": int(expires.timestamp()),
            },
            self.access_key,
            algorithm="HS256",
        )
        return Tokens(device.id, device.user_id, access, expires, refresh)

    def refresh(self, refresh_token: str) -> Tokens:
        now = self.clock.now()
        token = self.session.scalars(
            select(DeviceToken).where(DeviceToken.token_hash == _sha256(refresh_token))
        ).one_or_none()
        if token is None:
            raise AuthError("invalid_token")
        device = self.session.scalars(select(Device).where(Device.id == token.device_id).with_for_update()).one()
        if device.locked_at is not None:
            raise AuthError("device_locked")
        successors = self.session.scalars(select(DeviceToken).where(DeviceToken.predecessor_id == token.id)).all()
        if token.revoked_at is not None or any(s.first_used_at is not None for s in successors):
            # An old token after its successor was used, or a second token chain: theft signal.
            self.lock(device, "token_reuse")
            self.audit("token.reuse_locked", device.user_id, device.id)
            raise AuthError("device_locked")
        if token.first_used_at is None:
            token.first_used_at = now
            token.updated_at = now
            if token.predecessor_id is not None:
                siblings = self.session.scalars(
                    select(DeviceToken).where(
                        DeviceToken.predecessor_id == token.predecessor_id,
                        DeviceToken.id != token.id,
                        DeviceToken.first_used_at.is_(None),
                        DeviceToken.revoked_at.is_(None),
                    )
                ).all()
                for sibling in siblings:
                    sibling.revoked_at = now
                    sibling.updated_at = now
        # Otherwise T was used before and its successors were never used: a lost response; T stays valid.
        return self._issue(device, predecessor=token)

    def lock(self, device: Device, reason: str) -> None:
        now = self.clock.now()
        device.locked_at = now
        device.locked_reason = reason
        device.updated_at = now
        for token in self.session.scalars(
            select(DeviceToken).where(DeviceToken.device_id == device.id, DeviceToken.revoked_at.is_(None))
        ):
            token.revoked_at = now
            token.updated_at = now
        self.audit("device.locked", device.user_id, device.id, reason=reason)

    def authenticate(self, access_token: str | None) -> Device:
        if not access_token:
            raise AuthError("token_expired")
        try:
            claims = jwt.decode(
                access_token,
                self.access_key,
                algorithms=["HS256"],
                options={"verify_exp": False, "require": ["exp", "sub", "typ"]},
            )
        except jwt.PyJWTError:
            raise AuthError("token_expired") from None
        if claims.get("typ") != "access" or self.clock.now().timestamp() >= claims["exp"]:
            raise AuthError("token_expired")
        try:
            device = self.session.get(Device, uuid.UUID(claims["sub"]))
        except ValueError:
            raise AuthError("token_expired") from None
        if device is None:
            raise AuthError("token_expired")
        if device.locked_at is not None:
            raise AuthError("device_locked")
        return device
