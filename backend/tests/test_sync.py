"""Sync endpoint acceptance (BUILDPLAN 1.11.6). Scenario IDs from docs/spec-sync.md section 7."""

import threading
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AlarmFiring, AuditLog, Delivery, Device, Notification, SystemSetting, UserSettings
from app.db.rev import stamp, tombstone
from app.sync import protocol
from app.sync.protocol import iso
from tests.sync_helpers import make_user, notify


def op(op_type, payload, at=None, op_id=None, clock=None):
    return {"op_id": str(op_id or uuid.uuid4()), "type": op_type, "at": at or iso(clock.now()), "payload": payload}


def full_sync(phone, limit=500):
    changes, since, pages = [], 0, 0
    while True:
        body = phone.sync(since=since, limit=limit).json()
        changes += body["changes"]
        since, pages = body["next_since"], pages + 1
        if not body["has_more"]:
            return changes, since, pages


def test_S01_full_sync_paginates_in_rev_order(phones, sync_app, clock):
    a, _b = phones
    with sync_app.ctx.session_factory() as s:
        for _ in range(12):
            notify(s, clock, a.user_id)
        s.commit()
    changes, _since, pages = full_sync(a, limit=5)
    revs = [c["rev"] for c in changes]
    assert revs == sorted(revs) and len(revs) == len(set(revs))
    assert sum(c["table"] == "notifications" for c in changes) == 12 and pages >= 4


def test_S02_delta_only_newer_rows_across_tables(phones, sync_app, clock):
    a, _b = phones
    since = a.sync().json()["next_since"]
    with sync_app.ctx.session_factory() as s:
        notify(s, clock, a.user_id)
        settings = s.scalars(select(UserSettings).where(UserSettings.user_id == a.user_id)).one()
        settings.theme = "dark"
        stamp(s, settings, clock)
        s.commit()
    body = a.sync(since=since).json()
    assert [c["table"] for c in body["changes"]] == ["notifications", "user_settings"]
    assert all(c["rev"] > since for c in body["changes"])


def test_S03_invisible_rows_advance_next_since(phones, sync_app, clock):
    a, b = phones
    since = a.sync().json()["next_since"]
    with sync_app.ctx.session_factory() as s:
        for _ in range(5):
            notify(s, clock, b.user_id)  # invisible to A
        notify(s, clock, a.user_id)
        s.commit()
    body = a.sync(since=since, limit=3).json()
    assert body["changes"] == [] and body["has_more"] and body["next_since"] > since
    changes, _, _ = full_sync(a, limit=3)
    assert sum(c["table"] == "notifications" for c in changes) == 1


def test_S04_tombstone(phones, sync_app, clock):
    a, _ = phones
    with sync_app.ctx.session_factory() as s:
        n = notify(s, clock, a.user_id)
        s.commit()
        since = a.sync().json()["next_since"]
        tombstone(s, n, clock)
        s.commit()
        nid = str(n.id)
    [change] = a.sync(since=since).json()["changes"]
    assert change == {
        "table": "notifications",
        "id": nid,
        "rev": change["rev"],
        "deleted": True,
        "data": {"deleted_at": iso(clock.now())},
    }


def test_S05_other_users_settings_are_projected(phones, sync_app, clock):
    a, b = phones
    changes = a.sync().json()["changes"]
    other = next(c for c in changes if c["table"] == "user_settings" and c["data"]["user_id"] == str(b.user_id))
    assert set(other["data"]) == {"id", "user_id", "mode", "mode_until", "mode_schedule"}
    own = next(c for c in changes if c["table"] == "user_settings" and c["data"]["user_id"] == str(a.user_id))
    assert "quiet_hours" in own["data"]
    other_user = next(c for c in changes if c["table"] == "users" and c["id"] == str(b.user_id))
    assert set(other_user["data"]) == {"id", "name"}
    own_user = next(c for c in changes if c["table"] == "users" and c["id"] == str(a.user_id))
    assert "password_hash" not in own_user["data"] and own_user["data"]["time_zone"] == "Europe/Berlin"


def test_S06_resent_batch_is_idempotent(phones, sync_app, clock):
    a, _ = phones
    ops = [
        op("ack", {"display_key": "notif:x", "shown_at": iso(clock.now())}, clock=clock),
        op(
            "alarm_firing",
            {
                "planned_at": iso(clock.now()),
                "fired_at": iso(clock.now()),
                "alarm_type": "exact_idle",
                "idle": True,
                "network": True,
                "sync_result": "ok",
                "sync_ms": 120,
            },
            clock=clock,
        ),
    ]
    first = a.push(ops).json()["results"]
    second = a.push(ops).json()["results"]
    assert first == second and all(r["status"] == "ok" for r in first)
    with sync_app.ctx.session_factory() as s:
        assert len(s.scalars(select(AlarmFiring)).all()) == 1 and len(s.scalars(select(Delivery)).all()) == 1


def test_S11_future_timestamps_are_clamped(clock):
    from app.sync.push import clamp

    assert clamp(clock.now() + timedelta(minutes=10), clock.now()) == clock.now()
    assert clamp(clock.now() + timedelta(seconds=30), clock.now()) == clock.now() + timedelta(seconds=30)
    assert clamp(clock.now() - timedelta(weeks=6), clock.now()) == clock.now() - timedelta(weeks=6)


def test_S12_rejected_op_does_not_stop_the_batch(phones, sync_app, clock):
    a, _ = phones
    ops = [
        op("ack", {"display_key": ""}, clock=clock),
        op("ack", {"display_key": "notif:y", "shown_at": iso(clock.now())}, clock=clock),
        {"op_id": "not-a-uuid", "type": "ack", "at": iso(clock.now()), "payload": {}},
    ]
    results = a.push(ops).json()["results"]
    assert [r["status"] for r in results] == ["rejected", "ok", "rejected"]
    assert results[0]["code"] == "validation" and results[2]["op_id"] == "not-a-uuid"


def test_S13_transient_error_stops_the_batch(phones, sync_app, clock, monkeypatch):
    a, _ = phones
    from sqlalchemy.exc import OperationalError

    from app.sync import push

    def busy(ctx, payload):
        raise OperationalError("SELECT 1", {}, Exception("lock wait timeout"))

    monkeypatch.setitem(push.HANDLERS, "alarm_firing", busy)
    ops = [
        op("ack", {"display_key": "notif:z", "shown_at": iso(clock.now())}, clock=clock),
        op("alarm_firing", {}, clock=clock),
        op("ack", {"display_key": "notif:w", "shown_at": iso(clock.now())}, clock=clock),
    ]
    results = a.push(ops).json()["results"]
    assert [(r["status"], r.get("code")) for r in results] == [
        ("ok", None),
        ("retry", "busy"),
        ("retry", "not_processed"),
    ]
    monkeypatch.undo()
    resent = a.push(ops).json()["results"]
    assert resent[0]["status"] == "ok" and resent[2]["status"] == "ok"


def test_S14_unknown_op_type_is_retry(phones, clock):
    a, _ = phones
    results = a.push(
        [
            op("todo.future_thing", {}, clock=clock),
            op("ack", {"display_key": "k", "shown_at": iso(clock.now())}, clock=clock),
        ]
    ).json()["results"]
    assert results[0] == {"op_id": results[0]["op_id"], "status": "retry", "code": "unknown_op"}
    assert results[1]["code"] == "not_processed"


def test_S15_unknown_payload_fields_are_ignored(phones, clock):
    a, _ = phones
    payload = {"display_key": "k2", "shown_at": iso(clock.now()), "from_the_future": {"x": 1}}
    assert a.push([op("ack", payload, clock=clock)]).json()["results"][0]["status"] == "ok"


def test_S16_previous_protocol_version_still_served(phones, monkeypatch):
    a, _ = phones
    monkeypatch.setattr(protocol, "CURRENT_PROTOCOL", 2)
    a.protocol = 1
    response = a.sync()
    assert response.status_code == 200 and response.json()["meta"]["protocol"] == 1
    a.protocol = 2
    assert a.sync().json()["meta"]["protocol"] == 2


def test_S17_unsupported_protocol_and_too_old_app(phones, sync_app, clock):
    a, _ = phones
    a.protocol = 7
    response = a.sync()
    assert response.status_code == 400 and response.json()["error"]["code"] == "unsupported_protocol"
    assert "meta" in response.json()
    a.protocol = 1
    with sync_app.ctx.session_factory() as s:
        s.add(SystemSetting(key="sync.min_app_version", value=5, updated_at=clock.now()))
        s.commit()
    response = a.push([op("ack", {"display_key": "k", "shown_at": iso(clock.now())}, clock=clock)])
    assert response.status_code == 426 and response.json()["error"]["code"] == "app_too_old"
    assert response.json()["meta"]["min_app_version"] == 5
    a.app_version = 5
    assert a.sync().status_code == 200


def test_S18_expired_access_token(phones, clock):
    a, _ = phones
    clock.advance(minutes=16)
    response = a.sync()
    assert response.status_code == 401 and response.json()["error"]["code"] == "token_expired"


def test_S19_locked_device(phones, sync_app, clock):
    a, _ = phones
    from app.security.device_auth import DeviceAuth

    with sync_app.ctx.session_factory() as s:
        DeviceAuth(s, sync_app.ctx.settings.master_key_bytes, clock).lock(s.get(Device, a.device_id), "admin")
        s.commit()
    assert a.sync().json()["error"]["code"] == "device_locked"


def test_S22_double_ack_keeps_first_shown_at(phones, sync_app, clock):
    a, _ = phones
    first = iso(clock.now())
    a.push([op("ack", {"display_key": "nag:t@2026-01-15T09:00Z", "shown_at": first}, clock=clock)])
    clock.advance(minutes=1)
    a.push(
        [
            op(
                "ack",
                {"display_key": "nag:t@2026-01-15T09:00Z", "shown_at": iso(clock.now()), "acked_at": iso(clock.now())},
                clock=clock,
            )
        ]
    )
    with sync_app.ctx.session_factory() as s:
        [row] = s.scalars(select(Delivery)).all()
        assert iso(row.shown_at) == first and row.acked_at is not None and row.status == "acked"


def test_S23_device_status_and_alarm_firing_stay_on_the_device(phones, sync_app, clock):
    a, b = phones
    a.push(
        [
            op(
                "device_status",
                {"notifications_enabled": True, "channels": {"urgent_v1": 4}, "app_version": 1},
                clock=clock,
            )
        ]
    )
    a.push(
        [
            op(
                "device_status",
                {"notifications_enabled": True, "channels": {"urgent_v1": 0}, "app_version": 2},
                clock=clock,
            )
        ]
    )
    with sync_app.ctx.session_factory() as s:
        device = s.get(Device, a.device_id)
        assert device.app_version == 2 and device.device_status["channels"] == {"urgent_v1": 0}
        assert any(e.event == "device.notifications_muted" for e in s.scalars(select(AuditLog)))
    tables = {c["table"] for c in b.sync().json()["changes"]}
    assert tables <= {"users", "user_settings", "notifications"}


def test_S24_every_response_has_meta(phones, clock):
    a, _ = phones
    for response in (
        a.sync(),
        a.push([]),
        a.client.post("/api/devices/me/fcm-token", json={"token": "fcm-1"}, headers=a.headers()),
    ):
        assert response.status_code == 200
        m = response.json()["meta"]
        assert m["server_time"] == iso(clock.now()) and m["min_app_version"] == 1
        assert set(m["latest_app_version"]) == {"name", "code"} and "worker_heartbeat_age_s" in m


def test_fcm_token_and_last_sync(phones, sync_app, clock):
    a, _ = phones
    a.client.post("/api/devices/me/fcm-token", json={"token": "fcm-abc"}, headers=a.headers())
    a.sync()
    with sync_app.ctx.session_factory() as s:
        device = s.get(Device, a.device_id)
        assert device.fcm_token == "fcm-abc" and device.last_sync_at == clock.now()
    bad = a.client.post("/api/devices/me/fcm-token", json={"token": ""}, headers=a.headers())
    assert bad.status_code == 400 and "meta" in bad.json()


def test_push_limits(phones, clock):
    a, _ = phones
    too_many = [op("ack", {"display_key": f"k{i}", "shown_at": iso(clock.now())}, clock=clock) for i in range(101)]
    assert a.push(too_many).status_code == 400


def test_cli_test_notification(sync_app, phones, clock, capsys, monkeypatch, prod_settings):
    from app.cli import main as cli_main

    a, _ = phones
    monkeypatch.setattr("app.cli.get_settings", lambda: prod_settings)
    assert cli_main(["test-notification", "A"], clock=clock) == 0
    assert capsys.readouterr().out.startswith("created notif:")
    changes = a.sync().json()["changes"]
    assert any(c["table"] == "notifications" and c["data"]["kind"] == "test" for c in changes)


@pytest.mark.mariadb
def test_S20_concurrent_pushes(sync_app, clock):
    """Two devices push at the same time (MariaDB): every op applied once, revs unique."""
    with TestClient(sync_app) as client:
        from app.security.device_auth import DeviceAuth
        from tests.sync_helpers import HOST, Phone

        devices = []
        with sync_app.ctx.session_factory() as s:
            user = make_user(s, clock, "C")
            s.commit()
            auth = DeviceAuth(s, sync_app.ctx.settings.master_key_bytes, clock)
            for name in ("one", "two"):
                code, _ = auth.create_pairing_code(user)
                s.commit()
                t = client.post("/api/pair", json={"code": code, "device_name": name}, headers={"host": HOST}).json()
                devices.append(Phone(client, user.id, uuid.UUID(t["device_id"]), t["access_token"]))
        shared = [
            op("ack", {"display_key": f"notif:{i}", "shown_at": iso(clock.now())}, clock=clock) for i in range(20)
        ]
        errors = []

        def run(phone):
            try:
                for _ in range(3):
                    results = phone.push(shared).json()["results"]
                    assert all(r["status"] in ("ok", "retry") for r in results)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(d,)) for d in devices]
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
        assert errors == []
        with sync_app.ctx.session_factory() as s:
            assert len(s.scalars(select(Delivery)).all()) == 20  # each op_id applied once
            revs = [n.rev for n in s.scalars(select(Notification))]
            assert len(revs) == len(set(revs))
