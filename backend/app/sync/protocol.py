"""Protocol layer (spec-sync.md sections 1 and 6): headers, version checks, the meta envelope."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import Request
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.branding import app_version
from app.db.models import SystemSetting

CURRENT_PROTOCOL = 1
MIN_APP_VERSION_KEY = "sync.min_app_version"
DEFAULT_MIN_APP_VERSION = 1


def supported_protocols() -> tuple[int, ...]:
    """Current and previous protocol version (AGENTS.md section 5)."""
    return tuple(v for v in (CURRENT_PROTOCOL, CURRENT_PROTOCOL - 1) if v >= 1)


def iso(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def min_app_version(session: Session) -> int:
    row = session.get(SystemSetting, MIN_APP_VERSION_KEY)
    return int(row.value) if row is not None and row.value is not None else DEFAULT_MIN_APP_VERSION


def meta(session: Session, clock, protocol: int | None = None) -> dict:
    latest = app_version()
    return {
        "protocol": protocol or CURRENT_PROTOCOL,
        "server_time": iso(clock.now()),
        "min_app_version": min_app_version(session),
        "latest_app_version": {"name": latest["versionName"], "code": latest["versionCode"]},
        "worker_heartbeat_age_s": None,  # worker heartbeat arrives in 2.7.5
    }


@dataclass
class Client:
    protocol: int
    app_version: int


def check_client(request: Request, session: Session) -> Client:
    """Every sync request: supported protocol version and an app version at or above the minimum."""
    raw_protocol = request.headers.get("x-famapp-protocol", "")
    if not raw_protocol.isdigit() or int(raw_protocol) not in supported_protocols():
        raise ApiError(400, "unsupported_protocol", f"supported: {list(supported_protocols())}")
    raw_version = request.headers.get("x-famapp-app-version", "")
    if not raw_version.isdigit():
        raise ApiError(400, "validation", "X-Famapp-App-Version must be the app's versionCode")
    client = Client(int(raw_protocol), int(raw_version))
    if client.app_version < min_app_version(session):
        raise ApiError(426, "app_too_old", "update the app")
    request.state.protocol = client.protocol
    return client
