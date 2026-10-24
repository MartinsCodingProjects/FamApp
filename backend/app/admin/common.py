"""Shared pieces of the admin surface: DB session, templates, CSRF, system settings, audit."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Iterator
from datetime import datetime

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.admin.views import TEMPLATES
from app.db.models import AuditLog, SystemSetting
from app.security.client_ip import client_ip

SETUP_COMPLETED = "setup.completed_at"


def ctx(request: Request):
    return request.app.state.ctx


def db(request: Request) -> Iterator[Session]:
    with ctx(request).session_factory() as session:
        yield session


def render(request: Request, template: str, status_code: int = 200, **context) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, template, context, status_code=status_code)


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def hmac_hex(key: bytes, message: str) -> str:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def check_csrf(expected: str, given: str | None) -> None:
    if not given or not hmac.compare_digest(expected, given):
        raise HTTPException(status_code=403)


def get_setting(session: Session, key: str):
    row = session.get(SystemSetting, key)
    return None if row is None else row.value


def set_setting(session: Session, key: str, value, now: datetime) -> None:
    row = session.get(SystemSetting, key)
    if row is None:
        session.add(SystemSetting(key=key, value=value, updated_at=now))
    else:
        row.value = value
        row.updated_at = now


def setup_locked(session: Session) -> bool:
    return get_setting(session, SETUP_COMPLETED) is not None


def audit(session: Session, request: Request, event: str, user_id: uuid.UUID | None = None, **details) -> None:
    now = ctx(request).clock.now()
    session.add(
        AuditLog(
            at=now,
            created_at=now,
            updated_at=now,
            event=event,
            actor_user_id=user_id,
            ip=client_ip(request),
            details=details,
        )
    )


def cookie_options(request: Request, path: str) -> dict:
    return {"httponly": True, "samesite": "strict", "secure": not ctx(request).settings.dev, "path": path}
