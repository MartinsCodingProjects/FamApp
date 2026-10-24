from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db.migrations import schema_state

router = APIRouter()


@router.get("/api/health")
def health(request: Request) -> JSONResponse:
    state = schema_state(request.app.state.ctx.engine)
    if state.ready:
        return JSONResponse({"status": "ok", "schema": state.value})
    return JSONResponse({"status": "starting", "schema": state.value}, status_code=503)
