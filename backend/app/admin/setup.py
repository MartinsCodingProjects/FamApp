"""Setup wizard (README 10, spec-setup-wizard.md). Unreachable (404) once locked."""

from __future__ import annotations

import hmac
import json
import re
from zoneinfo import available_timezones

import segno
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin.common import (
    SETUP_COMPLETED,
    audit,
    check_csrf,
    cookie_options,
    ctx,
    db,
    get_setting,
    hmac_hex,
    redirect,
    render,
    set_setting,
    setup_locked,
)
from app.branding import branding
from app.db.models import User, UserSettings
from app.db.models.users import WEEKDAYS
from app.db.rev import stamp
from app.security import passwords, totp
from app.security.client_ip import client_ip
from app.security.secrets import SecretStore

router = APIRouter(prefix="/setup")
COOKIE = "famapp_setup"
STEPS = ("admin", "totp", "firebase", "user", "finish")
FIREBASE_SECRET = "firebase.service_account"
MAX_UPLOAD = 64 * 1024
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DEFAULT_TIME_ZONE = "Europe/Berlin"


def totp_secret_name(user: User) -> str:
    return f"user.{user.id.hex}.totp"


def session_cookie(request: Request) -> str:
    settings = ctx(request).settings
    return hmac_hex(settings.master_key_bytes, "setup-session:" + settings.setup_token.get_secret_value())


def csrf_token(request: Request) -> str:
    return hmac_hex(ctx(request).settings.master_key_bytes, "setup-csrf:" + session_cookie(request))


def secrets(request: Request, session: Session) -> SecretStore:
    return SecretStore(session, ctx(request).settings.master_key_bytes, ctx(request).clock)


def admin_user(session: Session) -> User | None:
    return session.scalars(select(User).where(User.role == "admin", User.deleted_at.is_(None))).first()


def second_user(session: Session) -> User | None:
    return session.scalars(select(User).where(User.role == "user", User.deleted_at.is_(None))).first()


def current_step(request: Request, session: Session) -> str:
    admin = admin_user(session)
    if admin is None:
        return "admin"
    if admin.totp_confirmed_at is None:
        return "totp"
    if not secrets(request, session).exists(FIREBASE_SECRET):
        return "firebase"
    if second_user(session) is None:
        return "user"
    return "finish"


def guard(request: Request, session: Session = Depends(db)) -> Session:
    """Every wizard page: 404 after the lock, token form without the setup cookie."""
    if setup_locked(session):
        raise HTTPException(status_code=404)
    given = request.cookies.get(COOKIE)
    if not given or not hmac.compare_digest(given, session_cookie(request)):
        raise HTTPException(status_code=303, headers={"Location": "/setup"})
    return session


def page(request: Request, session: Session, step: str, status_code: int = 200, **context):
    current = current_step(request, session)
    if step != current:
        return redirect(f"/setup/{current}")
    return render(
        request,
        f"setup_{step}.html",
        status_code,
        step=STEPS.index(step) + 1,
        steps=len(STEPS),
        csrf=csrf_token(request),
        min_password=passwords.MIN_LENGTH,
        **context,
    )


def new_user(session: Session, request: Request, name: str, role: str, time_zone: str) -> User:
    clock = ctx(request).clock
    user = User(name=name, role=role, time_zone=time_zone)
    stamp(session, user, clock)
    session.add(user)
    session.flush()
    settings = UserSettings(user_id=user.id)
    stamp(session, settings, clock)
    session.add(settings)
    return user


# --- token -------------------------------------------------------------------------------


@router.get("")
def token_form(request: Request, session: Session = Depends(db)):
    if setup_locked(session):
        raise HTTPException(status_code=404)
    given = request.cookies.get(COOKIE)
    if given and hmac.compare_digest(given, session_cookie(request)):
        return redirect(f"/setup/{current_step(request, session)}")
    return render(request, "setup_token.html")


@router.post("")
def token_submit(request: Request, token: str = Form(""), session: Session = Depends(db)):
    if setup_locked(session):
        raise HTTPException(status_code=404)
    limiter = request.app.state.setup_limiter
    key = client_ip(request)
    if limiter.blocked(key):
        return render(request, "setup_token.html", 429, error="admin.error.rateLimited")
    expected = ctx(request).settings.setup_token.get_secret_value()
    if not hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        limiter.hit(key)
        audit(session, request, "setup.token_failed")
        session.commit()
        return render(request, "setup_token.html", 401, error="admin.error.tokenWrong")
    response = redirect(f"/setup/{current_step(request, session)}")
    response.set_cookie(COOKIE, session_cookie(request), **cookie_options(request, "/setup"))
    return response


# --- admin account -------------------------------------------------------------------------


@router.get("/admin")
def admin_form(request: Request, session: Session = Depends(guard)):
    return page(request, session, "admin")


def name_error(session: Session, name: str) -> str | None:
    if not 1 <= len(name) <= 100:
        return "admin.error.nameInvalid"
    exists = session.scalar(select(func.count()).select_from(User).where(func.lower(User.name) == name.lower()))
    return "admin.error.nameTaken" if exists else None


@router.post("/admin")
def admin_submit(
    request: Request,
    name: str = Form(""),
    password: str = Form(""),
    password_repeat: str = Form(""),
    csrf: str = Form(""),
    session: Session = Depends(guard),
):
    check_csrf(csrf_token(request), csrf)
    if current_step(request, session) != "admin":
        return redirect(f"/setup/{current_step(request, session)}")
    name = name.strip()
    error = name_error(session, name)
    if not error and len(password) < passwords.MIN_LENGTH:
        error = "admin.error.passwordShort"
    if not error and password != password_repeat:
        error = "admin.error.passwordMismatch"
    if error:
        return page(request, session, "admin", 400, error=error, name=name)
    user = new_user(session, request, name, "admin", DEFAULT_TIME_ZONE)
    user.password_hash = passwords.hash_password(password)
    secrets(request, session).set(totp_secret_name(user), totp.new_secret(), actor_user_id=user.id)
    audit(session, request, "setup.admin_created", user.id)
    session.commit()
    return redirect("/setup/totp")


# --- TOTP ----------------------------------------------------------------------------------


def totp_context(request: Request, session: Session) -> dict:
    user = admin_user(session)
    secret = secrets(request, session).get(totp_secret_name(user)).get_secret_value()
    uri = totp.provisioning_uri(secret, user.name, branding()["displayName"])
    # Colors come from the semantic tokens color.qr.foreground/background via admin.css (.qr-code, .qr-line).
    qr = segno.make(uri, error="m").svg_inline(scale=5, border=4, light=None, svgclass="qr-code", lineclass="qr-line")
    return {"secret": secret, "qr_svg": qr}


@router.get("/totp")
def totp_form(request: Request, session: Session = Depends(guard)):
    if current_step(request, session) != "totp":
        return redirect(f"/setup/{current_step(request, session)}")
    return page(request, session, "totp", **totp_context(request, session))


@router.post("/totp")
def totp_submit(request: Request, code: str = Form(""), csrf: str = Form(""), session: Session = Depends(guard)):
    check_csrf(csrf_token(request), csrf)
    if current_step(request, session) != "totp":
        return redirect(f"/setup/{current_step(request, session)}")
    user = admin_user(session)
    secret = secrets(request, session).get(totp_secret_name(user)).get_secret_value()
    now = ctx(request).clock.now()
    step = totp.verify(secret, code, now, user.totp_last_step)
    if step is None:
        return page(request, session, "totp", 400, error="admin.error.codeWrong", **totp_context(request, session))
    user.totp_last_step = step
    user.totp_confirmed_at = now
    stamp(session, user, ctx(request).clock)
    audit(session, request, "setup.totp_confirmed", user.id)
    session.commit()
    return redirect("/setup/firebase")


# --- Firebase ------------------------------------------------------------------------------


def parse_service_account(raw: bytes) -> dict | None:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("type") != "service_account":
        return None
    if not all(isinstance(data.get(k), str) and data[k] for k in ("project_id", "client_email", "private_key")):
        return None
    if not data["private_key"].startswith("-----BEGIN PRIVATE KEY-----"):
        return None
    return data


@router.get("/firebase")
def firebase_form(request: Request, session: Session = Depends(guard)):
    return page(request, session, "firebase")


@router.post("/firebase")
async def firebase_submit(
    request: Request, file: UploadFile | None = None, csrf: str = Form(""), session: Session = Depends(guard)
):
    check_csrf(csrf_token(request), csrf)
    if current_step(request, session) != "firebase":
        return redirect(f"/setup/{current_step(request, session)}")
    raw = await file.read(MAX_UPLOAD + 1) if file is not None else b""
    data = parse_service_account(raw) if len(raw) <= MAX_UPLOAD else None
    if data is None:
        return page(request, session, "firebase", 400, error="admin.error.firebaseInvalid")
    admin = admin_user(session)
    secrets(request, session).set(FIREBASE_SECRET, json.dumps(data), actor_user_id=admin.id)
    set_setting(session, "firebase.project_id", data["project_id"], ctx(request).clock.now())
    audit(session, request, "setup.firebase_stored", admin.id, project_id=data["project_id"])
    session.commit()
    return redirect("/setup/user")


# --- second account ------------------------------------------------------------------------


def time_zones() -> list[str]:
    return sorted(z for z in available_timezones() if "/" in z and not z.startswith(("Etc/", "SystemV/")))


@router.get("/user")
def user_form(request: Request, session: Session = Depends(guard)):
    return page(
        request,
        session,
        "user",
        time_zones=time_zones(),
        time_zone=DEFAULT_TIME_ZONE,
        quiet_start="22:00",
        quiet_end="06:00",
    )


@router.post("/user")
def user_submit(
    request: Request,
    name: str = Form(""),
    time_zone: str = Form(DEFAULT_TIME_ZONE),
    quiet_start: str = Form("22:00"),
    quiet_end: str = Form("06:00"),
    csrf: str = Form(""),
    session: Session = Depends(guard),
):
    check_csrf(csrf_token(request), csrf)
    if current_step(request, session) != "user":
        return redirect(f"/setup/{current_step(request, session)}")
    name = name.strip()
    error = name_error(session, name)
    if not error and time_zone not in available_timezones():
        error = "admin.error.timeZoneInvalid"
    if not error and not (TIME.match(quiet_start) and TIME.match(quiet_end)):
        error = "admin.error.timeInvalid"
    if error:
        return page(
            request,
            session,
            "user",
            400,
            error=error,
            name=name,
            time_zones=time_zones(),
            time_zone=time_zone,
            quiet_start=quiet_start,
            quiet_end=quiet_end,
        )
    clock = ctx(request).clock
    user = new_user(session, request, name, "user", time_zone)
    session.flush()
    quiet = {day: {"start": quiet_start, "end": quiet_end} for day in WEEKDAYS}
    for account in (admin_user(session), user):
        account.time_zone = time_zone
        stamp(session, account, clock)
        settings = session.scalars(select(UserSettings).where(UserSettings.user_id == account.id)).one()
        settings.quiet_hours = quiet
        stamp(session, settings, clock)
    audit(session, request, "setup.user_created", admin_user(session).id, created_user_id=str(user.id))
    session.commit()
    return redirect("/setup/finish")


# --- finish --------------------------------------------------------------------------------


@router.get("/finish")
def finish_form(request: Request, session: Session = Depends(guard)):
    admin, user = admin_user(session), second_user(session)
    quiet = None
    if user is not None:
        settings = session.scalars(select(UserSettings).where(UserSettings.user_id == user.id)).one()
        quiet = settings.quiet_hours["mon"]
    return page(
        request,
        session,
        "finish",
        admin=admin,
        user=user,
        quiet=quiet,
        project_id=get_setting(session, "firebase.project_id"),
    )


@router.post("/finish")
def finish_submit(request: Request, csrf: str = Form(""), session: Session = Depends(guard)):
    check_csrf(csrf_token(request), csrf)
    if current_step(request, session) != "finish":
        return redirect(f"/setup/{current_step(request, session)}")
    now = ctx(request).clock.now()
    set_setting(session, SETUP_COMPLETED, now.isoformat(), now)
    audit(session, request, "setup.completed", admin_user(session).id)
    session.commit()
    response = redirect("/login")
    response.delete_cookie(COOKIE, path="/setup")
    return response
