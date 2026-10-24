"""Device auth acceptance (BUILDPLAN 1.10.9): lost response + retry, weeks offline, theft locks,
spoofed CF-Connecting-IP ignored; plus pairing, revocation, rate limits."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.cli import main as cli_main
from app.db.models import AuditLog, Device, User, UserSettings
from app.db.rev import stamp
from app.main import create_app
from app.security.device_auth import DeviceAuth
from tests.cf_keys import AUD, TEAM, FakeTeam

APP = {"host": "famapp.cowflex.com"}


@pytest.fixture
def app(prod_settings, clock, engine):
    from app.security.cf_access import AccessVerifier

    return create_app(prod_settings, clock, AccessVerifier(TEAM, AUD, clock, fetch=FakeTeam().jwks))


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def user(app, clock):
    with app.ctx.session_factory() as s:
        u = User(name="Partner", role="user", time_zone="Europe/Berlin")
        stamp(s, u, clock)
        s.add(u)
        s.flush()
        st = UserSettings(user_id=u.id)
        stamp(s, st, clock)
        s.add(st)
        s.commit()
        return u.id


def new_code(app, clock, user_id) -> str:
    with app.ctx.session_factory() as s:
        code, _ = DeviceAuth(s, app.ctx.settings.master_key_bytes, clock).create_pairing_code(s.get(User, user_id))
        s.commit()
        return code


def pair(client, code, name="Pixel"):
    return client.post("/api/pair", json={"code": code, "device_name": name}, headers=APP)


def refresh(client, token, **headers):
    return client.post("/api/auth/refresh", json={"refresh_token": token}, headers={**APP, **headers})


def events(app) -> list[str]:
    with app.ctx.session_factory() as s:
        return [a.event for a in s.scalars(select(AuditLog).order_by(AuditLog.at))]


def test_pairing_creates_device_and_tokens(client, app, clock, user):
    code = new_code(app, clock, user)
    assert len(code) == 9 and code[4] == "-"
    response = pair(client, code.lower().replace("-", " "))
    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == str(user) and body["access_token"] and body["refresh_token"]
    assert body["access_expires_at"].endswith("Z")
    assert pair(client, code).json()["error"]["code"] == "pairing_failed"  # one-time
    assert "device.paired" in events(app) and "pairing.failed" in events(app)


def test_pairing_code_expires_after_10_minutes(client, app, clock, user):
    code = new_code(app, clock, user)
    clock.advance(minutes=10)
    response = pair(client, code)
    assert response.status_code == 401 and response.json()["error"]["code"] == "pairing_failed"


def test_pairing_rate_limit_per_ip(client, app, clock, user):
    for _ in range(10):
        assert pair(client, "AAAA-AAAA").status_code == 401
    code = new_code(app, clock, user)
    response = pair(client, code)
    assert response.status_code == 429 and int(response.headers["retry-after"]) > 0
    clock.advance(minutes=15)
    assert pair(client, new_code(app, clock, user)).status_code == 201


def test_lost_refresh_response_and_retry(client, app, clock, user):
    tokens = pair(client, new_code(app, clock, user)).json()
    first = refresh(client, tokens["refresh_token"])
    assert first.status_code == 200
    # the response with the successor got lost; the device retries with its stored token
    retry = refresh(client, tokens["refresh_token"])
    assert retry.status_code == 200
    again = refresh(client, tokens["refresh_token"])  # and once more, still fine
    assert again.status_code == 200
    # the device finally stores the last successor and keeps going
    assert refresh(client, again.json()["refresh_token"]).status_code == 200
    assert "token.reuse_locked" not in events(app)


def test_weeks_offline(client, app, clock, user):
    tokens = pair(client, new_code(app, clock, user)).json()
    clock.advance(timedelta(weeks=8))
    response = refresh(client, tokens["refresh_token"])
    assert response.status_code == 200
    me = client.post(
        "/api/devices/me/pairing-codes", headers={**APP, "authorization": f"Bearer {response.json()['access_token']}"}
    )
    assert me.status_code == 201


def test_theft_locks_the_device(client, app, clock, user):
    tokens = pair(client, new_code(app, clock, user)).json()
    stolen = tokens["refresh_token"]
    legit = refresh(client, stolen).json()["refresh_token"]
    assert refresh(client, legit).status_code == 200  # the device used its successor
    response = refresh(client, stolen)  # the thief shows up with the old token
    assert response.status_code == 401 and response.json()["error"]["code"] == "device_locked"
    with app.ctx.session_factory() as s:
        device = s.scalars(select(Device)).one()
        assert device.locked_reason == "token_reuse"
    # the legitimate chain is locked too
    assert refresh(client, legit).json()["error"]["code"] == "device_locked"
    assert "token.reuse_locked" in events(app) and "device.locked" in events(app)


def test_second_chain_locks(client, app, clock, user):
    tokens = pair(client, new_code(app, clock, user)).json()
    a = refresh(client, tokens["refresh_token"]).json()["refresh_token"]
    b = refresh(client, tokens["refresh_token"]).json()["refresh_token"]  # lost response → sibling
    assert refresh(client, b).status_code == 200  # b is used, a is revoked
    assert refresh(client, a).json()["error"]["code"] == "device_locked"


def test_access_token_expiry_and_lock(client, app, clock, user):
    tokens = pair(client, new_code(app, clock, user)).json()
    auth = {**APP, "authorization": f"Bearer {tokens['access_token']}"}
    assert client.post("/api/devices/me/pairing-codes", headers=auth).status_code == 201
    clock.advance(minutes=15)
    response = client.post("/api/devices/me/pairing-codes", headers=auth)
    assert response.status_code == 401 and response.json()["error"]["code"] == "token_expired"
    assert (
        client.post("/api/devices/me/pairing-codes", headers={**APP, "authorization": "Bearer garbage"}).json()[
            "error"
        ]["code"]
        == "token_expired"
    )
    fresh = refresh(client, tokens["refresh_token"]).json()
    with app.ctx.session_factory() as s:
        device = s.scalars(select(Device)).one()
        DeviceAuth(s, app.ctx.settings.master_key_bytes, clock).lock(device, "admin")
        s.commit()
    response = client.post(
        "/api/devices/me/pairing-codes", headers={**APP, "authorization": f"Bearer {fresh['access_token']}"}
    )
    assert response.json()["error"]["code"] == "device_locked"
    assert refresh(client, fresh["refresh_token"]).json()["error"]["code"] == "device_locked"


def test_device_creates_code_for_its_own_user(client, app, clock, user):
    tokens = pair(client, new_code(app, clock, user)).json()
    auth = {**APP, "authorization": f"Bearer {tokens['access_token']}"}
    code = client.post("/api/devices/me/pairing-codes", headers=auth).json()["code"]
    second = pair(client, code, name="New phone").json()
    assert second["user_id"] == str(user)
    for _ in range(4):
        assert client.post("/api/devices/me/pairing-codes", headers=auth).status_code == 201
    assert client.post("/api/devices/me/pairing-codes", headers=auth).status_code == 429


def test_spoofed_cf_connecting_ip_is_ignored(app, clock, user):
    """A request straight to the VPS IP (through Traefik, not Cloudflare) with a forged CF-Connecting-IP
    is keyed by its real address, so rotating the header does not escape the pairing rate limit."""
    with TestClient(app, client=("10.0.1.5", 50000)) as traefik:  # requests arrive from Traefik
        for n in range(10):
            headers = {**APP, "x-forwarded-for": "198.51.100.4", "cf-connecting-ip": f"6.6.6.{n}"}
            assert (
                traefik.post("/api/pair", json={"code": "AAAA-AAAA", "device_name": "x"}, headers=headers).status_code
                == 401
            )
        headers = {**APP, "x-forwarded-for": "198.51.100.4", "cf-connecting-ip": "6.6.6.99"}
        response = traefik.post(
            "/api/pair", json={"code": new_code(app, clock, user), "device_name": "x"}, headers=headers
        )
        assert response.status_code == 429
        # a real Cloudflare hop with a different visitor is a different key
        headers = {**APP, "x-forwarded-for": "172.70.1.2", "cf-connecting-ip": "203.0.113.9"}
        response = traefik.post(
            "/api/pair", json={"code": new_code(app, clock, user), "device_name": "x"}, headers=headers
        )
        assert response.status_code == 201
    with app.ctx.session_factory() as s:
        ips = {a.ip for a in s.scalars(select(AuditLog)) if a.event == "pairing.failed"}
    assert ips == {"198.51.100.4"}


def test_cli_pairing_code_and_lock(app, clock, user, capsys, monkeypatch, prod_settings):
    monkeypatch.setattr("app.cli.get_settings", lambda: prod_settings)
    assert cli_main(["pairing-code", "partner"], clock=clock) == 0
    code = capsys.readouterr().out.split()[0]
    with TestClient(app) as client:
        assert pair(client, code).status_code == 201
    with app.ctx.session_factory() as s:
        device_id = str(s.scalars(select(Device)).one().id)
    assert cli_main(["lock-device", device_id], clock=clock) == 0
    assert cli_main(["pairing-code", "nobody"], clock=clock) == 1


def test_validation_errors_have_the_error_shape(client):
    response = client.post("/api/pair", json={"code": ""}, headers=APP)
    assert response.status_code == 400 and response.json()["error"]["code"] == "validation"
