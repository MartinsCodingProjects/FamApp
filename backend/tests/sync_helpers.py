"""Fixtures for sync tests: an app, two users with one paired device each."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.db.models import Notification, User, UserSettings
from app.db.rev import stamp
from app.main import create_app
from app.security.cf_access import AccessVerifier
from app.security.device_auth import DeviceAuth
from tests.cf_keys import AUD, TEAM, FakeTeam

HOST = "famapp.cowflex.com"


@dataclass
class Phone:
    client: TestClient
    user_id: uuid.UUID
    device_id: uuid.UUID
    access: str
    protocol: int = 1
    app_version: int = 1

    def headers(self, **extra) -> dict:
        return {
            "host": HOST,
            "authorization": f"Bearer {self.access}",
            "x-famapp-protocol": str(self.protocol),
            "x-famapp-app-version": str(self.app_version),
            **extra,
        }

    def sync(self, since=0, limit=500, **headers):
        return self.client.get("/api/sync", params={"since": since, "limit": limit}, headers=self.headers(**headers))

    def push(self, ops, **headers):
        return self.client.post("/api/sync/push", json={"ops": ops}, headers=self.headers(**headers))


def make_user(session, clock, name: str) -> User:
    user = User(name=name, role="user", time_zone="Europe/Berlin")
    stamp(session, user, clock)
    session.add(user)
    session.flush()
    settings = UserSettings(user_id=user.id)
    stamp(session, settings, clock)
    session.add(settings)
    return user


def notify(session, clock, user_id, key="notification.test.title") -> Notification:
    n = Notification(user_id=user_id, kind="test", message_key=key, params={}, show_at=clock.now())
    stamp(session, n, clock)
    session.add(n)
    return n


@pytest.fixture
def sync_app(prod_settings, clock, engine):
    return create_app(prod_settings, clock, AccessVerifier(TEAM, AUD, clock, fetch=FakeTeam().jwks))


@pytest.fixture
def phones(sync_app, clock):
    with TestClient(sync_app) as client:
        result = []
        with sync_app.ctx.session_factory() as s:
            users = [make_user(s, clock, "A"), make_user(s, clock, "B")]
            s.commit()
            auth = DeviceAuth(s, sync_app.ctx.settings.master_key_bytes, clock)
            for user in users:
                code, _ = auth.create_pairing_code(user)
                s.commit()
                tokens = client.post(
                    "/api/pair", json={"code": code, "device_name": user.name}, headers={"host": HOST}
                ).json()
                result.append(Phone(client, user.id, uuid.UUID(tokens["device_id"]), tokens["access_token"]))
        yield result
