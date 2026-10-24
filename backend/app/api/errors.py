"""API errors: {"error": {"code", "message"}} (spec-sync.md section 5; 1.11 adds the meta envelope)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str = "", headers: dict | None = None) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers or {}


def error_body(code: str, message: str = "") -> dict:
    return {"error": {"code": code, "message": message}}


# The sync endpoints answer every error with the meta envelope too (spec-sync.md section 1).
META_PATHS = ("/api/sync", "/api/devices/me/fcm-token")


def _body(request: Request, code: str, message: str) -> dict:
    body = error_body(code, message)
    if request.url.path.startswith(META_PATHS):
        from app.sync.protocol import meta

        with request.app.state.ctx.session_factory() as session:
            body = {
                "meta": meta(session, request.app.state.ctx.clock, getattr(request.state, "protocol", None)),
                **body,
            }
    return body


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(_body(request, exc.code, exc.message), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = ", ".join(".".join(str(p) for p in e["loc"][1:]) for e in exc.errors())  # names only, no values
        return JSONResponse(_body(request, "validation", f"invalid fields: {fields}"), status_code=400)
