"""Device pairing and token endpoints (spec-device-auth.md)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db.models import Device, User
from app.security.client_ip import client_ip
from app.security.device_auth import AuthError, DeviceAuth
from app.security.ratelimit import RateLimiter

router = APIRouter(prefix="/api")


def limiters(clock) -> dict[str, RateLimiter]:
    return {
        "pair": RateLimiter(10, timedelta(minutes=15), clock),
        "refresh": RateLimiter(30, timedelta(minutes=15), clock),
        "pairing_code": RateLimiter(5, timedelta(hours=1), clock),
    }


def db(request: Request) -> Iterator[Session]:
    with request.app.state.ctx.session_factory() as session:
        yield session


def device_auth(request: Request, session: Session) -> DeviceAuth:
    ctx = request.app.state.ctx
    return DeviceAuth(session, ctx.settings.master_key_bytes, ctx.clock, ip=client_ip(request))


def auth_failed(session: Session, error: AuthError) -> ApiError:
    session.commit()  # keep audit entries and a reuse lock even though the request fails
    return ApiError(401, error.code)


def rate_limited(request: Request, session: Session, auth: DeviceAuth, limiter: RateLimiter, action: str) -> ApiError:
    auth.audit("rate_limited", action=action)
    session.commit()
    return ApiError(429, "rate_limited", headers={"Retry-After": str(limiter.retry_after())})


@dataclass
class CurrentDevice:
    device: Device
    user: User


def current_device(request: Request, session: Session = Depends(db)) -> CurrentDevice:
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else None
    try:
        device = device_auth(request, session).authenticate(token)
    except AuthError as error:
        raise ApiError(401, error.code) from None
    return CurrentDevice(device, session.get(User, device.user_id))


class PairRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    device_name: str = Field(min_length=1, max_length=100)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=200)


@router.post("/pair", status_code=201)
def pair(body: PairRequest, request: Request, session: Session = Depends(db)) -> JSONResponse:
    auth = device_auth(request, session)
    limiter = request.app.state.limiters["pair"]
    key = client_ip(request)
    if limiter.blocked(key):
        raise rate_limited(request, session, auth, limiter, "pair")
    try:
        tokens = auth.pair(body.code, body.device_name.strip())
    except AuthError as error:
        limiter.hit(key)
        raise auth_failed(session, error) from None
    session.commit()
    return JSONResponse(tokens.as_json(), status_code=201)


@router.post("/auth/refresh")
def refresh(body: RefreshRequest, request: Request, session: Session = Depends(db)) -> JSONResponse:
    auth = device_auth(request, session)
    limiter = request.app.state.limiters["refresh"]
    key = client_ip(request)
    if limiter.blocked(key):
        raise rate_limited(request, session, auth, limiter, "refresh")
    limiter.hit(key)
    try:
        tokens = auth.refresh(body.refresh_token)
    except AuthError as error:
        raise auth_failed(session, error) from None
    session.commit()
    return JSONResponse(tokens.as_json())


@router.post("/devices/me/pairing-codes", status_code=201)
def create_pairing_code(
    request: Request, me: CurrentDevice = Depends(current_device), session: Session = Depends(db)
) -> JSONResponse:
    auth = device_auth(request, session)
    limiter = request.app.state.limiters["pairing_code"]
    keys = (f"ip:{client_ip(request)}", f"device:{me.device.id}")
    if any(limiter.blocked(k) for k in keys):
        raise rate_limited(request, session, auth, limiter, "pairing_code")
    for k in keys:
        limiter.hit(k)
    user = session.get(User, me.user.id)
    code, expires = auth.create_pairing_code(user, created_by_device=session.get(Device, me.device.id))
    session.commit()
    return JSONResponse({"code": code, "expires_at": expires.isoformat().replace("+00:00", "Z")}, status_code=201)
