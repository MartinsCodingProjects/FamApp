"""ASGI entry point: `uvicorn app.main:create_app --factory` (spec-backend-skeleton.md).

Two FastAPI apps behind one dispatcher: the admin surface for the admin host (dev: the admin
port), the app surface for everything else.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.types import ASGIApp, Receive, Scope, Send

from app.admin import auth as admin_auth
from app.admin import setup as admin_setup
from app.api import devices, errors, health
from app.clock import Clock, SystemClock
from app.config import Settings, get_settings
from app.db.session import make_engine, make_session_factory
from app.log import request_id_var, setup_logging
from app.security.cf_access import HEADER as CF_HEADER
from app.security.cf_access import AccessVerifier
from app.security.client_ip import networks
from app.security.ratelimit import RateLimiter

log = logging.getLogger("app.access")
REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
ADMIN_STATIC = Path(__file__).parent / "admin/static"


@dataclass
class AppContext:
    settings: Settings
    engine: Engine
    clock: Clock
    session_factory: sessionmaker[Session] = field(init=False)

    def __post_init__(self) -> None:
        self.session_factory = make_session_factory(self.engine)


def _fastapi(ctx: AppContext) -> FastAPI:
    dev = ctx.settings.dev
    app = FastAPI(
        docs_url="/docs" if dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if dev else None,
    )
    app.state.ctx = ctx
    return app


def build_app_surface(ctx: AppContext) -> FastAPI:
    app = _fastapi(ctx)
    errors.install(app)
    app.state.limiters = devices.limiters(ctx.clock)
    app.state.trusted_proxies = networks(ctx.settings.trusted_proxies)
    app.include_router(health.router)
    app.include_router(devices.router)
    return app


def build_admin_surface(ctx: AppContext, verifier: AccessVerifier | None) -> ASGIApp:
    app = _fastapi(ctx)
    app.mount("/static", StaticFiles(directory=ADMIN_STATIC), name="static")
    app.state.setup_limiter = RateLimiter(5, timedelta(minutes=15), ctx.clock)
    app.state.login_limiter = RateLimiter(10, timedelta(minutes=15), ctx.clock)
    app.state.trusted_proxies = networks(ctx.settings.trusted_proxies)
    app.include_router(admin_setup.router)
    app.include_router(admin_auth.router)
    if ctx.settings.dev:
        return app
    assert verifier is not None
    return CloudflareAccessGuard(app, verifier)


async def not_found(send: Send) -> None:
    body = b'{"detail":"Not Found"}'
    await send(
        {
            "type": "http.response.start",
            "status": 404,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


class CloudflareAccessGuard:
    """Every admin request needs a valid Cloudflare Access JWT, otherwise 404."""

    def __init__(self, app: ASGIApp, verifier: AccessVerifier) -> None:
        self.app = app
        self.verifier = verifier

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            token = _header(scope, CF_HEADER.encode())
            if not self.verifier.verify(token):
                if scope["type"] == "http":
                    await not_found(send)
                return
        await self.app(scope, receive, send)


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1")
    return None


def _host(scope: Scope) -> str:
    host = (_header(scope, b"host") or "").strip().lower()
    return host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"


class Dispatcher:
    """Routes requests to the admin or app surface; adds request IDs and the access log line."""

    def __init__(self, ctx: AppContext, app_surface: ASGIApp, admin_surface: ASGIApp) -> None:
        self.ctx = ctx
        self.app_surface = app_surface
        self.admin_surface = admin_surface

    def is_admin(self, scope: Scope) -> bool:
        settings = self.ctx.settings
        if settings.dev:
            server = scope.get("server") or (None, None)
            return server[1] == settings.admin_dev_port
        return _host(scope) == settings.admin_host.lower()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._lifespan(receive, send)
            return
        target = self.admin_surface if self.is_admin(scope) else self.app_surface
        if scope["type"] != "http":
            await target(scope, receive, send)
            return
        incoming = _header(scope, b"x-request-id")
        request_id = incoming if incoming and REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        status = {"code": 500}
        started = time.perf_counter()

        async def send_with_id(message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message = {**message, "headers": [*message.get("headers", []), (b"x-request-id", request_id.encode())]}
            await send(message)

        try:
            await target(scope, receive, send_with_id)
        finally:
            log.info(
                "request",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),  # never the query string
                    "status": status["code"],
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    "surface": "admin" if target is self.admin_surface else "app",
                },
            )
            request_id_var.reset(token)

    async def _lifespan(self, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                self.ctx.engine.dispose()
                await send({"type": "lifespan.shutdown.complete"})
                return


def create_app(
    settings: Settings | None = None, clock: Clock | None = None, verifier: AccessVerifier | None = None
) -> Dispatcher:
    settings = settings or get_settings()
    setup_logging(settings.log_level)
    clock = clock or SystemClock()
    ctx = AppContext(settings=settings, engine=make_engine(settings.database_url), clock=clock)
    if verifier is None and not settings.dev:
        verifier = AccessVerifier(settings.cf_access_team_domain, settings.cf_access_aud, clock)
    return Dispatcher(ctx, build_app_surface(ctx), build_admin_surface(ctx, verifier))
