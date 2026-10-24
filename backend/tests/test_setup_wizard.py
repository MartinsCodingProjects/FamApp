"""Setup wizard and admin login, full flow and guards (BUILDPLAN 1.9, spec-setup-wizard.md)."""

import json
import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AuditLog, User, UserSettings
from app.main import create_app
from app.security import totp
from app.security.secrets import SecretStore

SERVICE_ACCOUNT = {
    "type": "service_account",
    "project_id": "famapp-test",
    "client_email": "fcm@famapp-test.iam.gserviceaccount.com",
    "private_key": "-----BEGIN PRIVATE KEY-----\nnot-a-real-key\n-----END PRIVATE KEY-----\n",
}
PASSWORD = "correct horse battery"


@pytest.fixture
def app(dev_settings, clock, engine):
    settings = dev_settings.model_copy(update={"admin_dev_port": 80})  # TestClient talks to port 80
    return create_app(settings, clock)


@pytest.fixture
def client(app):
    with TestClient(app, follow_redirects=False) as client:
        yield client


def csrf(response) -> str:
    return re.search(r'name="csrf" value="([0-9a-f]+)"', response.text).group(1)


def secret_from(response) -> str:
    return re.search(r'data-testid="totp-secret">([A-Z2-7]+)<', response.text).group(1)


def enter_token(client, app):
    token = app.ctx.settings.setup_token.get_secret_value()
    response = client.post("/setup", data={"token": token})
    assert response.status_code == 303
    return response


def run_wizard(client, app, clock):
    enter_token(client, app)
    page = client.get("/setup/admin")
    assert page.status_code == 200 and "Schritt 1 von 5" in page.text
    response = client.post(
        "/setup/admin", data={"name": "Admin", "password": PASSWORD, "password_repeat": PASSWORD, "csrf": csrf(page)}
    )
    assert response.headers["location"] == "/setup/totp"
    page = client.get("/setup/totp")
    secret = secret_from(page)
    assert "<svg" in page.text
    response = client.post("/setup/totp", data={"code": totp.code_at(secret, clock.now()), "csrf": csrf(page)})
    assert response.headers["location"] == "/setup/firebase"
    page = client.get("/setup/firebase")
    response = client.post(
        "/setup/firebase",
        data={"csrf": csrf(page)},
        files={"file": ("sa.json", json.dumps(SERVICE_ACCOUNT), "application/json")},
    )
    assert response.headers["location"] == "/setup/user"
    page = client.get("/setup/user")
    assert 'value="Europe/Berlin" selected' in page.text
    response = client.post(
        "/setup/user",
        data={
            "name": "Partner",
            "time_zone": "Europe/Vienna",
            "quiet_start": "21:30",
            "quiet_end": "06:30",
            "csrf": csrf(page),
        },
    )
    assert response.headers["location"] == "/setup/finish"
    page = client.get("/setup/finish")
    assert "famapp-test" in page.text and "Partner" in page.text and "21:30" in page.text
    response = client.post("/setup/finish", data={"csrf": csrf(page)})
    assert response.headers["location"] == "/login"
    return secret


def login(client, secret, clock, password=PASSWORD, name="Admin"):
    return client.post("/login", data={"name": name, "password": password, "code": totp.code_at(secret, clock.now())})


def test_full_flow_then_login_and_logout(client, app, clock, engine):
    secret = run_wizard(client, app, clock)
    with app.ctx.session_factory() as s:
        users = {u.name: u for u in s.scalars(select(User))}
        assert users["Admin"].role == "admin" and users["Partner"].role == "user"
        assert {u.time_zone for u in users.values()} == {"Europe/Vienna"}
        settings = s.scalars(select(UserSettings)).all()
        assert all(st.quiet_hours["sun"] == {"start": "21:30", "end": "06:30"} for st in settings)
        stored = SecretStore(s, app.ctx.settings.master_key_bytes, clock).get("firebase.service_account")
        assert json.loads(stored.get_secret_value())["project_id"] == "famapp-test"
        assert users["Admin"].password_hash.startswith("$argon2id$")
    assert client.get("/").headers["location"] == "/login"
    clock.advance(seconds=30)  # next TOTP step (the wizard's code is used up)
    response = login(client, secret, clock)
    assert response.status_code == 303 and response.headers["location"] == "/"
    home = client.get("/")
    assert home.status_code == 200 and "Angemeldet als Admin" in home.text
    response = client.post("/logout", data={"csrf": csrf(home)})
    assert response.headers["location"] == "/login"
    assert client.get("/").headers["location"] == "/login"
    with app.ctx.session_factory() as s:
        events = [a.event for a in s.scalars(select(AuditLog).order_by(AuditLog.at))]
    for event in (
        "setup.admin_created",
        "setup.totp_confirmed",
        "setup.firebase_stored",
        "setup.user_created",
        "setup.completed",
        "admin.login",
        "admin.logout",
    ):
        assert event in events


def test_wizard_is_gone_after_lock(client, app, clock):
    run_wizard(client, app, clock)
    for path in ("/setup", "/setup/admin", "/setup/totp", "/setup/finish"):
        assert client.get(path).status_code == 404
    token = app.ctx.settings.setup_token.get_secret_value()
    assert client.post("/setup", data={"token": token}).status_code == 404


def test_wrong_token_and_rate_limit(client, app, clock):
    for _ in range(5):
        response = client.post("/setup", data={"token": "wrong"})
        assert response.status_code == 401 and "Setup-Token stimmt nicht" in response.text
    token = app.ctx.settings.setup_token.get_secret_value()
    assert client.post("/setup", data={"token": token}).status_code == 429
    clock.advance(minutes=15)
    assert client.post("/setup", data={"token": token}).status_code == 303
    with app.ctx.session_factory() as s:
        assert len([a for a in s.scalars(select(AuditLog)) if a.event == "setup.token_failed"]) == 5


def test_steps_need_the_setup_cookie_and_order(client, app):
    assert client.get("/setup/admin").headers["location"] == "/setup"
    enter_token(client, app)
    assert client.get("/setup/finish").headers["location"] == "/setup/admin"
    assert client.get("/setup").headers["location"] == "/setup/admin"
    assert client.get("/").headers["location"] == "/setup"
    assert client.get("/login").headers["location"] == "/setup"


def test_csrf_required(client, app):
    enter_token(client, app)
    response = client.post("/setup/admin", data={"name": "Admin", "password": PASSWORD, "password_repeat": PASSWORD})
    assert response.status_code == 403
    response = client.post(
        "/setup/admin", data={"name": "Admin", "password": PASSWORD, "password_repeat": PASSWORD, "csrf": "0" * 64}
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"name": "", "password": PASSWORD, "password_repeat": PASSWORD}, "1 bis 100 Zeichen"),
        ({"name": "Admin", "password": "short", "password_repeat": "short"}, "mindestens 12 Zeichen"),
        ({"name": "Admin", "password": PASSWORD, "password_repeat": PASSWORD + "x"}, "stimmen nicht"),
    ],
)
def test_admin_step_validation(client, app, data, message):
    enter_token(client, app)
    page = client.get("/setup/admin")
    response = client.post("/setup/admin", data={**data, "csrf": csrf(page)})
    assert response.status_code == 400 and message in response.text


def test_wrong_totp_code(client, app, clock):
    enter_token(client, app)
    page = client.get("/setup/admin")
    client.post(
        "/setup/admin", data={"name": "Admin", "password": PASSWORD, "password_repeat": PASSWORD, "csrf": csrf(page)}
    )
    page = client.get("/setup/totp")
    response = client.post("/setup/totp", data={"code": "000000", "csrf": csrf(page)})
    assert response.status_code == 400 and "Code stimmt nicht" in response.text
    assert client.get("/setup/firebase").headers["location"] == "/setup/totp"


@pytest.mark.parametrize(
    "content",
    [
        b"not json",
        json.dumps({**SERVICE_ACCOUNT, "type": "user"}).encode(),
        json.dumps({**SERVICE_ACCOUNT, "private_key": "nope"}).encode(),
        b"x" * (64 * 1024 + 1),
    ],
    ids=["garbage", "wrong-type", "bad-key", "too-big"],
)
def test_firebase_validation(client, app, clock, content):
    enter_token(client, app)
    page = client.get("/setup/admin")
    client.post(
        "/setup/admin", data={"name": "Admin", "password": PASSWORD, "password_repeat": PASSWORD, "csrf": csrf(page)}
    )
    page = client.get("/setup/totp")
    client.post("/setup/totp", data={"code": totp.code_at(secret_from(page), clock.now()), "csrf": csrf(page)})
    page = client.get("/setup/firebase")
    response = client.post("/setup/firebase", data={"csrf": csrf(page)}, files={"file": ("sa.json", content)})
    assert response.status_code == 400 and "keine gültige Dienstkonto-Datei" in response.text


def test_login_failures_lockout_and_totp_replay(client, app, clock):
    secret = run_wizard(client, app, clock)
    clock.advance(seconds=30)
    assert login(client, secret, clock, name="Partner").status_code == 401  # not an admin
    assert login(client, secret, clock, name="Nobody").status_code == 401
    for _ in range(5):
        response = login(client, secret, clock, password="wrong password!")
        assert response.status_code == 401 and "Anmeldung fehlgeschlagen" in response.text
    assert login(client, secret, clock).status_code == 401  # locked, even with the right password
    clock.advance(minutes=15)
    assert login(client, secret, clock).status_code == 303
    assert login(client, secret, clock).status_code == 401  # same TOTP step again = replay
    with app.ctx.session_factory() as s:
        events = [a.event for a in s.scalars(select(AuditLog))]
    assert "admin.locked" in events and events.count("admin.login_failed") >= 7


def test_session_expires_after_idle_time(client, app, clock):
    secret = run_wizard(client, app, clock)
    clock.advance(seconds=30)
    login(client, secret, clock)
    assert client.get("/").status_code == 200
    clock.advance(timedelta(hours=11))
    assert client.get("/").status_code == 200
    clock.advance(timedelta(hours=12))
    assert client.get("/").headers["location"] == "/login"


def test_cookie_flags_outside_dev(prod_settings, clock, engine):
    from app.security.cf_access import AccessVerifier
    from tests.cf_keys import AUD, TEAM, FakeTeam

    team = FakeTeam()
    app = create_app(prod_settings, clock, AccessVerifier(TEAM, AUD, clock, fetch=team.jwks))
    with TestClient(app, follow_redirects=False) as client:
        response = client.post(
            "/setup",
            data={"token": prod_settings.setup_token.get_secret_value()},
            headers={"host": "famapp-admin.cowflex.com", "Cf-Access-Jwt-Assertion": team.token(clock)},
        )
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie and "Path=/setup" in cookie
