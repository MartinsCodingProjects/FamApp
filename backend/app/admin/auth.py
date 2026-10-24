"""Admin login with password + TOTP and server-side sessions (spec-setup-wizard.md)."""

from __future__ import annotations

import hashlib
import secrets as stdlib_secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin.common import audit, check_csrf, cookie_options, ctx, db, redirect, render, setup_locked
from app.admin.setup import secrets, totp_secret_name
from app.db.models import AdminSession, User
from app.security import passwords, totp

router = APIRouter()
COOKIE = "famapp_admin"
IDLE_TIMEOUT = timedelta(hours=12)
MAX_AGE = timedelta(days=7)
MAX_FAILURES = 5
LOCKOUT = timedelta(minutes=15)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def current_session(request: Request, session: Session) -> AdminSession | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = session.scalars(select(AdminSession).where(AdminSession.token_hash == _hash(token))).one_or_none()
    now = ctx(request).clock.now()
    if row is None or now >= row.expires_at or now - row.last_seen_at >= IDLE_TIMEOUT:
        return None
    row.last_seen_at = now
    session.commit()
    return row


class Admin:
    def __init__(self, user: User, admin_session: AdminSession) -> None:
        self.user = user
        self.session = admin_session


def require_admin(request: Request, session: Session = Depends(db)) -> Admin:
    """Admin pages: wizard first, then a valid admin session, else the login page."""
    if not setup_locked(session):
        raise HTTPException(status_code=303, headers={"Location": "/setup"})
    row = current_session(request, session)
    if row is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return Admin(session.get(User, row.user_id), row)


@router.get("/")
def home(request: Request, admin: Admin = Depends(require_admin)):
    return render(request, "home.html", user=admin.user, csrf=admin.session.csrf_token)


@router.get("/login")
def login_form(request: Request, session: Session = Depends(db)):
    if not setup_locked(session):
        return redirect("/setup")
    return render(request, "login.html")


@router.post("/login")
def login_submit(
    request: Request,
    name: str = Form(""),
    password: str = Form(""),
    code: str = Form(""),
    session: Session = Depends(db),
):
    if not setup_locked(session):
        return redirect("/setup")
    clock = ctx(request).clock
    now = clock.now()
    user = session.scalars(
        select(User).where(func.lower(User.name) == name.strip().lower(), User.deleted_at.is_(None))
    ).one_or_none()

    def fail(reason: str):
        if user is not None:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILURES:
                user.locked_until = now + LOCKOUT
                user.failed_logins = 0
                audit(session, request, "admin.locked", user.id)
        audit(session, request, "admin.login_failed", user.id if user else None, reason=reason)
        session.commit()
        return render(request, "login.html", 401, error="admin.error.loginFailed", name=name)

    if user is None or user.role != "admin" or user.totp_confirmed_at is None:
        passwords.verify_password(None, password)  # same work as a real check
        return fail("unknown_user")
    if user.locked_until is not None and now < user.locked_until:
        return fail("locked")
    if not passwords.verify_password(user.password_hash, password):
        return fail("password")
    secret = secrets(request, session).get(totp_secret_name(user)).get_secret_value()
    step = totp.verify(secret, code, now, user.totp_last_step)
    if step is None:
        return fail("code")
    user.totp_last_step = step
    user.failed_logins = 0
    user.locked_until = None
    token = stdlib_secrets.token_urlsafe(32)
    session.add(
        AdminSession(
            user_id=user.id,
            token_hash=_hash(token),
            csrf_token=stdlib_secrets.token_hex(32),
            created_at=now,
            updated_at=now,
            last_seen_at=now,
            expires_at=now + MAX_AGE,
        )
    )
    audit(session, request, "admin.login", user.id)
    session.commit()
    response = redirect("/")
    response.set_cookie(COOKIE, token, max_age=int(MAX_AGE.total_seconds()), **cookie_options(request, "/"))
    return response


@router.post("/logout")
def logout(
    request: Request, csrf: str = Form(""), admin: Admin = Depends(require_admin), session: Session = Depends(db)
):
    check_csrf(admin.session.csrf_token, csrf)
    row = session.get(AdminSession, admin.session.id)
    if row is not None:
        session.delete(row)
    audit(session, request, "admin.logout", admin.user.id)
    session.commit()
    response = redirect("/login")
    response.delete_cookie(COOKIE, path="/")
    return response
