"""Sync endpoints (spec-sync.md): GET /api/sync, POST /api/sync/push, POST /api/devices/me/fcm-token."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.devices import CurrentDevice, current_device, db
from app.api.errors import ApiError
from app.db.models import Device
from app.sync import handlers  # noqa: F401  (registers the op handlers)
from app.sync.delta import DEFAULT_LIMIT, MAX_LIMIT, delta
from app.sync.protocol import Client, check_client, meta
from app.sync.push import MAX_OPS, Rejected, apply_ops, parse_op

router = APIRouter(prefix="/api")


def client(request: Request, session: Session = Depends(db)) -> Client:
    return check_client(request, session)


@router.get("/sync")
def get_sync(
    request: Request,
    since: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    version: Client = Depends(client),
    me: CurrentDevice = Depends(current_device),
    session: Session = Depends(db),
) -> dict:
    clock = request.app.state.ctx.clock
    body = delta(session, me.user.id, since, limit)
    device = session.get(Device, me.device.id)
    device.last_sync_at = clock.now()
    session.commit()
    return {"meta": meta(session, clock, version.protocol), **body}


@router.post("/sync/push")
def push(
    request: Request,
    body: dict = Body(...),
    version: Client = Depends(client),
    me: CurrentDevice = Depends(current_device),
    session: Session = Depends(db),
) -> dict:
    raw_ops = body.get("ops")
    if not isinstance(raw_ops, list) or len(raw_ops) > MAX_OPS:
        raise ApiError(400, "validation", f"ops must be a list of at most {MAX_OPS} operations")
    clock = request.app.state.ctx.clock
    parsed, results_before = [], {}
    for index, raw in enumerate(raw_ops):
        try:
            parsed.append(parse_op(raw if isinstance(raw, dict) else {}))
        except Rejected as rejection:
            # Without a valid op_id nothing can be stored; report it in place.
            op_id = raw.get("op_id") if isinstance(raw, dict) else None
            results_before[index] = {
                "op_id": op_id,
                "status": "rejected",
                "code": rejection.code,
                "message": rejection.message,
            }
            parsed.append(None)
    device = session.get(Device, me.device.id)
    applied = iter(apply_ops(session, device, clock, [op for op in parsed if op is not None]))
    results = [results_before[i] if op is None else next(applied) for i, op in enumerate(parsed)]
    return {"meta": meta(session, clock, version.protocol), "results": results}


@router.post("/devices/me/fcm-token")
def fcm_token(
    request: Request,
    body: dict = Body(...),
    version: Client = Depends(client),
    me: CurrentDevice = Depends(current_device),
    session: Session = Depends(db),
) -> dict:
    token = body.get("token")
    if not isinstance(token, str) or not 1 <= len(token) <= 4096:
        raise ApiError(400, "validation", "token must be 1-4096 characters")
    clock = request.app.state.ctx.clock
    device = session.get(Device, me.device.id)
    device.fcm_token = token
    device.fcm_token_updated_at = clock.now()
    device.updated_at = clock.now()
    session.commit()
    return {"meta": meta(session, clock, version.protocol)}
