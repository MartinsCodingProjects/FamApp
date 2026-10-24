"""Operation handlers of protocol 1 that exist so far (spec-sync.md section 3). Todo operations
arrive with Run 3; importing this module registers the handlers."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import AlarmFiring, AuditLog, Delivery
from app.sync.push import OpContext, Rejected, handler

ALARM_TYPES = {"alarm_clock", "exact_idle"}
SYNC_RESULTS = {"ok", "timeout", "error", "no_network"}


def _time(payload: dict, name: str, required: bool = True) -> datetime | None:
    value = payload.get(name)
    if value is None:
        if required:
            raise Rejected("validation", f"{name} is required")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise Rejected("validation", f"{name} must be an ISO timestamp") from None
    if parsed.tzinfo is None:
        raise Rejected("validation", f"{name} must include a time zone")
    return parsed


def _bool(payload: dict, name: str, required: bool = True) -> bool | None:
    value = payload.get(name)
    if value is None and not required:
        return None
    if not isinstance(value, bool):
        raise Rejected("validation", f"{name} must be true or false")
    return value


@handler("ack")
def ack(ctx: OpContext, payload: dict) -> None:
    key = payload.get("display_key")
    if not isinstance(key, str) or not 1 <= len(key) <= 255:
        raise Rejected("validation", "display_key must be 1-255 characters")
    shown_at = _time(payload, "shown_at")
    opened_at = _time(payload, "opened_at", required=False)
    acked_at = _time(payload, "acked_at", required=False)
    now = ctx.clock.now()

    def find():
        return ctx.session.scalars(
            select(Delivery).where(Delivery.display_key == key, Delivery.device_id == ctx.device.id)
        ).one_or_none()

    row = find()
    if row is None:
        try:
            with ctx.session.begin_nested():
                row = Delivery(
                    display_key=key,
                    device_id=ctx.device.id,
                    created_at=now,
                    updated_at=now,
                    status="planned",
                    retries=0,
                )
                ctx.session.add(row)
        except IntegrityError:
            row = find()  # a concurrent ack for the same key and device won the insert
    # Later acks only fill fields that are still empty (S22).
    row.shown_at = row.shown_at or shown_at
    row.opened_at = row.opened_at or opened_at
    row.acked_at = row.acked_at or acked_at
    row.status = "acked" if row.acked_at else "shown"
    row.updated_at = now


@handler("device_status")
def device_status(ctx: OpContext, payload: dict) -> None:
    enabled = _bool(payload, "notifications_enabled")
    channels = payload.get("channels", {})
    if not isinstance(channels, dict) or not all(
        isinstance(k, str) and isinstance(v, int) for k, v in channels.items()
    ):
        raise Rejected("validation", "channels must map channel ids to importance integers")
    version = payload.get("app_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise Rejected("validation", "app_version must be the versionCode")
    status = {"notifications_enabled": enabled, "channels": channels}
    battery = _bool(payload, "battery_optimization_ignored", required=False)
    if battery is not None:
        status["battery_optimization_ignored"] = battery
    device = ctx.device
    previous = device.device_status or {}
    muted_before = {k for k, v in previous.get("channels", {}).items() if v == 0}
    muted_now = {k for k, v in channels.items() if v == 0}
    now = ctx.clock.now()
    if (previous.get("notifications_enabled", True) and not enabled) or (muted_now - muted_before):
        ctx.session.add(
            AuditLog(
                at=now,
                created_at=now,
                updated_at=now,
                event="device.notifications_muted",
                actor_user_id=device.user_id,
                actor_device_id=device.id,
                details={"notifications_enabled": enabled, "muted_channels": sorted(muted_now)},
            )
        )
    device.device_status = status
    device.app_version = version
    device.updated_at = now


@handler("alarm_firing")
def alarm_firing(ctx: OpContext, payload: dict) -> None:
    alarm_type = payload.get("alarm_type")
    sync_result = payload.get("sync_result")
    if alarm_type not in ALARM_TYPES:
        raise Rejected("validation", f"alarm_type must be one of {sorted(ALARM_TYPES)}")
    if sync_result not in SYNC_RESULTS:
        raise Rejected("validation", f"sync_result must be one of {sorted(SYNC_RESULTS)}")
    sync_ms = payload.get("sync_ms")
    if sync_ms is not None and (not isinstance(sync_ms, int) or isinstance(sync_ms, bool) or sync_ms < 0):
        raise Rejected("validation", "sync_ms must be a non-negative integer")
    now = ctx.clock.now()
    ctx.session.add(
        AlarmFiring(
            device_id=ctx.device.id,
            planned_at=_time(payload, "planned_at"),
            fired_at=_time(payload, "fired_at"),
            alarm_type=alarm_type,
            idle=_bool(payload, "idle"),
            network=_bool(payload, "network"),
            sync_result=sync_result,
            sync_ms=sync_ms,
            created_at=now,
            updated_at=now,
        )
    )
