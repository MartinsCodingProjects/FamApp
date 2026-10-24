"""TOTP (RFC 6238, 30 s, 6 digits) with the time provider and replay protection."""

from __future__ import annotations

import hmac
from datetime import datetime

import pyotp

STEP_SECONDS = 30
WINDOW = 1  # accept the previous and the next step too


def new_secret() -> str:
    return pyotp.random_base32(32)  # 160 bit


def provisioning_uri(secret: str, account: str, issuer: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)


def code_at(secret: str, when: datetime) -> str:
    return pyotp.TOTP(secret).at(when)


def verify(secret: str, code: str, now: datetime, last_step: int | None) -> int | None:
    """Return the matched time step, or None. A step at or before last_step is a replay."""
    code = code.strip().replace(" ", "")
    if not (len(code) == 6 and code.isdigit()):
        return None
    totp = pyotp.TOTP(secret)
    current = int(now.timestamp()) // STEP_SECONDS
    for step in range(current - WINDOW, current + WINDOW + 1):
        if hmac.compare_digest(totp.generate_otp(step), code):
            if last_step is not None and step <= last_step:
                return None
            return step
    return None
