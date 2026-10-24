"""Surfaces, host separation, health, request IDs and access logs (spec-backend-skeleton.md)."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table

from app.db import migrations
from app.main import create_app
from app.security.cf_access import AccessVerifier
from tests.cf_keys import AUD, TEAM, FakeTeam

APP = "famapp.cowflex.com"
ADMIN = "famapp-admin.cowflex.com"


@pytest.fixture
def team():
    return FakeTeam()


@pytest.fixture
def prod_client(prod_settings, clock, team, bare_engine):
    app = create_app(prod_settings, clock, AccessVerifier(TEAM, AUD, clock, fetch=team.jwks))
    with TestClient(app) as client:
        yield client


def get(client, path, host, **headers):
    return client.get(path, headers={"host": host, **headers})


def migrate(settings):
    from app.db.session import make_engine

    engine = make_engine(settings.database_url)
    migrations.upgrade(engine)
    return engine


def stamp(engine, revision):
    table = Table("alembic_version", MetaData(), autoload_with=engine)
    with engine.begin() as conn:
        conn.execute(table.update().values(version_num=revision))


def test_health_follows_the_schema(prod_client, prod_settings):
    response = get(prod_client, "/api/health", APP)
    assert response.status_code == 503 and response.json() == {"status": "starting", "schema": "empty"}
    engine = migrate(prod_settings)
    assert get(prod_client, "/api/health", APP).json() == {"status": "ok", "schema": "head"}
    stamp(engine, "f00dfeedcafe")  # a revision this code does not know = newer image migrated
    response = get(prod_client, "/api/health", APP)
    assert response.status_code == 200 and response.json()["schema"] == "newer"
    engine.dispose()


def test_health_behind_is_not_ready(prod_client, prod_settings, monkeypatch):
    migrate(prod_settings).dispose()
    known = migrations.code_revisions()[1]
    monkeypatch.setattr(migrations, "code_revisions", lambda: ("9999", {*known, "9999"}))
    response = get(prod_client, "/api/health", APP)
    assert response.status_code == 503 and response.json()["schema"] == "behind"


def test_health_unreachable_db(prod_settings, clock, tmp_path):
    settings = prod_settings.model_copy(update={"database_url": f"sqlite:///{tmp_path}/missing/dir/x.db"})
    with TestClient(create_app(settings, clock, AccessVerifier(TEAM, AUD, clock, fetch=FakeTeam().jwks))) as client:
        response = get(client, "/api/health", APP)
    assert response.status_code == 503 and response.json()["schema"] == "unreachable"


def test_admin_host_needs_cloudflare_access(prod_client, prod_settings, team, clock):
    migrate(prod_settings).dispose()
    assert get(prod_client, "/", ADMIN).status_code == 404
    assert get(prod_client, "/", ADMIN, **{"Cf-Access-Jwt-Assertion": "garbage"}).status_code == 404
    other_aud = team.token(clock, aud="another-app")
    assert get(prod_client, "/", ADMIN, **{"Cf-Access-Jwt-Assertion": other_aud}).status_code == 404
    response = get(prod_client, "/setup", ADMIN, **{"Cf-Access-Jwt-Assertion": team.token(clock)})
    assert response.status_code == 200 and '<html lang="de">' in response.text
    # Host normalization: case and port
    response = get(
        prod_client, "/setup", "FAMAPP-ADMIN.cowflex.com:443", **{"Cf-Access-Jwt-Assertion": team.token(clock)}
    )
    assert response.status_code == 200


def test_missing_jwt_looks_like_a_missing_page(prod_client, team, clock):
    blocked = get(prod_client, "/", ADMIN)
    missing = get(prod_client, "/nope", ADMIN, **{"Cf-Access-Jwt-Assertion": team.token(clock)})
    assert blocked.status_code == missing.status_code == 404
    assert blocked.json() == missing.json()


def test_surfaces_are_separate(prod_client, team, clock):
    jwt_header = {"Cf-Access-Jwt-Assertion": team.token(clock)}
    assert get(prod_client, "/api/health", ADMIN, **jwt_header).status_code == 404
    assert get(prod_client, "/", APP).status_code == 404
    assert get(prod_client, "/static/tokens.generated.css", APP).status_code == 404
    # direct IP access and container health checks land on the app surface
    assert get(prod_client, "/api/health", "203.0.113.7:8000").status_code in (200, 503)


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_api_docs_in_production(prod_client, team, clock, path):
    assert get(prod_client, path, APP).status_code == 404
    assert get(prod_client, path, ADMIN, **{"Cf-Access-Jwt-Assertion": team.token(clock)}).status_code == 404


def test_dev_mode_admin_on_admin_port_without_jwt(dev_settings, clock, engine):
    settings = dev_settings.model_copy(update={"admin_dev_port": 80})  # TestClient's server port
    with TestClient(create_app(settings, clock)) as client:
        assert client.get("/setup").status_code == 200
        assert client.get("/api/health").status_code == 404
    with TestClient(create_app(dev_settings, clock)) as client:
        assert client.get("/api/health").status_code in (200, 503)
        assert client.get("/docs").status_code == 200


def test_admin_static_files(prod_client, prod_settings, team, clock):
    migrate(prod_settings).dispose()
    jwt_header = {"Cf-Access-Jwt-Assertion": team.token(clock)}
    page = get(prod_client, "/setup", ADMIN, **jwt_header).text
    assert "tokens.generated.css" in page and "htmx.min.js" in page and "FamApp Admin" in page
    css = get(prod_client, "/static/tokens.generated.css", ADMIN, **jwt_header)
    assert css.status_code == 200 and "--color-state-urgent" in css.text
    assert get(prod_client, "/static/htmx.min.js", ADMIN, **jwt_header).status_code == 200


def test_request_id_and_access_log(prod_client, caplog):
    caplog.set_level(logging.INFO, logger="app.access")
    response = get(prod_client, "/api/health?title=Geheim", APP, **{"X-Request-ID": "abcdef12-3456"})
    assert response.headers["x-request-id"] == "abcdef12-3456"
    generated = get(prod_client, "/api/health", APP, **{"X-Request-ID": "bad id!"}).headers["x-request-id"]
    assert generated != "bad id!" and len(generated) == 32
    [first, _second] = [r for r in caplog.records if r.name == "app.access"]
    assert first.path == "/api/health" and first.status in (200, 503) and first.method == "GET"
    assert "Geheim" not in json.dumps({k: str(v) for k, v in first.__dict__.items()})


def test_json_log_format():
    from app.log import JsonFormatter, request_id_var

    record = logging.makeLogRecord(
        {"name": "x", "levelname": "INFO", "msg": "hello %s", "args": ("you",), "path": "/p"}
    )
    token = request_id_var.set("rid-12345678")
    try:
        entry = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert entry["msg"] == "hello you" and entry["request_id"] == "rid-12345678" and entry["path"] == "/p"
    assert entry["level"] == "info" and entry["ts"].endswith("+00:00")
