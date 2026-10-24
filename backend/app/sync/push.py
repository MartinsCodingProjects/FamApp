"""Push: ordered, idempotent operations with per-op results (spec-sync.md sections 1, 3, 5.2)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.clock import Clock
from app.db.models import Device, ProcessedOp

log = logging.getLogger(__name__)
MAX_OPS = 100
FUTURE_TOLERANCE = timedelta(seconds=60)


class Rejected(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.message = message


@dataclass
class OpContext:
    session: Session
    device: Device
    clock: Clock
    at: datetime  # corrected and clamped action time


Handler = Callable[[OpContext, dict], None]
HANDLERS: dict[str, Handler] = {}


def handler(op_type: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        HANDLERS[op_type] = fn
        return fn

    return register


def clamp(at: datetime, now: datetime) -> datetime:
    return now if at > now + FUTURE_TOLERANCE else at


def apply_ops(session: Session, device: Device, clock: Clock, ops: list[dict]) -> list[dict]:
    results: list[dict] = []
    stop = False
    for op in ops:
        op_id = op["op_id"]
        if stop:
            results.append({"op_id": str(op_id), "status": "retry", "code": "not_processed"})
            continue
        stored = session.get(ProcessedOp, op_id)
        if stored is not None:
            results.append({"op_id": str(op_id), **stored.result})
            continue
        fn = HANDLERS.get(op["type"])
        if fn is None:
            results.append({"op_id": str(op_id), "status": "retry", "code": "unknown_op"})
            stop = True
            continue
        now = clock.now()
        try:
            result = {"status": "ok"}
            try:
                fn(OpContext(session, device, clock, clamp(op["at"], now)), op["payload"])
            except Rejected as rejection:
                session.rollback()
                result = {"status": "rejected", "code": rejection.code}
                if rejection.message:
                    result["message"] = rejection.message
            session.add(ProcessedOp(op_id=op_id, device_id=device.id, type=op["type"], result=result, processed_at=now))
            session.commit()
        except IntegrityError:
            # The same op_id was committed concurrently (resend while the first request runs).
            session.rollback()
            stored = session.get(ProcessedOp, op_id)
            if stored is None:
                results.append({"op_id": str(op_id), "status": "retry", "code": "busy"})
                stop = True
                continue
            result = stored.result
        except OperationalError:
            session.rollback()
            log.warning("op hit a transient database error", extra={"op_type": op["type"]}, exc_info=True)
            results.append({"op_id": str(op_id), "status": "retry", "code": "busy"})
            stop = True
            continue
        results.append({"op_id": str(op_id), **result})
    return results


def parse_op(raw: dict) -> dict:
    """Envelope check; payload validation is the handler's job. Raises Rejected."""
    try:
        op_id = uuid.UUID(str(raw["op_id"]))
    except (KeyError, ValueError):
        raise Rejected("validation", "op_id must be a UUID") from None
    op_type = raw.get("type")
    payload = raw.get("payload", {})
    if not isinstance(op_type, str) or not isinstance(payload, dict):
        raise Rejected("validation", "type must be a string and payload an object")
    try:
        at = datetime.fromisoformat(str(raw["at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        raise Rejected("validation", "at must be an ISO timestamp") from None
    if at.tzinfo is None:
        raise Rejected("validation", "at must include a time zone")
    return {"op_id": op_id, "type": op_type, "at": at, "payload": payload}
