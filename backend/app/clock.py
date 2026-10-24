"""Time provider. Logic code gets "now" only from a Clock (AGENTS.md section 5, A1).

This file is the one place allowed to read the system clock (tools/arch_check.py).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Current time, timezone-aware, in UTC."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock:
    """Controllable clock for tests: set "now" and fast-forward."""

    def __init__(self, start: datetime) -> None:
        self._now = _require_aware(start)

    def now(self) -> datetime:
        return self._now

    def set(self, value: datetime) -> None:
        self._now = _require_aware(value)

    def advance(self, delta: timedelta | None = None, **kwargs: float) -> datetime:
        """Move forward by a timedelta or by timedelta keyword arguments (minutes=15)."""
        step = delta if delta is not None else timedelta(**kwargs)
        if step < timedelta(0):
            raise ValueError("FakeClock only moves forward; use set() to jump back")
        self._now += step
        return self._now


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Clock times must be timezone-aware")
    return value.astimezone(UTC)
