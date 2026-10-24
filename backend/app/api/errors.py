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


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = ", ".join(".".join(str(p) for p in e["loc"][1:]) for e in exc.errors())  # names only, no values
        return JSONResponse(error_body("validation", f"invalid fields: {fields}"), status_code=400)
