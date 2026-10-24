"""Secret encryption and store (BUILDPLAN 1.8.3)."""

import os

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.config import ConfigError, load_settings
from app.db.models import AuditLog, Secret
from app.security import crypto
from app.security.secrets import SecretStore

KEY = os.urandom(32)


def test_roundtrip_and_random_nonce():
    a = crypto.encrypt(KEY, "firebase.service_account", b'{"type": "service_account"}')
    b = crypto.encrypt(KEY, "firebase.service_account", b'{"type": "service_account"}')
    assert a != b and a[0] == 1
    assert crypto.decrypt(KEY, "firebase.service_account", a) == b'{"type": "service_account"}'


def flip(blob: bytes, index: int) -> bytes:
    return blob[:index] + bytes([blob[index] ^ 0x01]) + blob[index + 1 :]


@pytest.mark.parametrize("index", [1, 5, 12, 13, -1], ids=["nonce-start", "nonce", "nonce-end", "body", "tag"])
def test_tampering_is_detected(index):
    blob = crypto.encrypt(KEY, "x.y", b"value")
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(KEY, "x.y", flip(blob, index))


def test_swapped_associated_data():
    blob = crypto.encrypt(KEY, "google.client_secret", b"value")
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(KEY, "firebase.service_account", blob)


def test_wrong_key():
    blob = crypto.encrypt(KEY, "x.y", b"value")
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(os.urandom(32), "x.y", blob)


@pytest.mark.parametrize("blob", [b"", b"\x01short", b"\x02" + bytes(40)], ids=["empty", "short", "version"])
def test_malformed_ciphertext(blob):
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(KEY, "x.y", blob)


def test_missing_or_bad_master_key(session, clock, monkeypatch):
    with pytest.raises(ValueError):
        SecretStore(session, b"", clock)
    with pytest.raises(ValueError):
        crypto.encrypt(b"short", "x.y", b"v")
    monkeypatch.delenv("MASTER_KEY", raising=False)
    with pytest.raises(ConfigError, match="MASTER_KEY is not set"):
        load_settings(
            dev=False,
            database_url="sqlite://",
            setup_token="s" * 32,
            cf_access_team_domain="t.cloudflareaccess.com",
            cf_access_aud="a",
            master_key=None,
        )


def test_store_set_get_exists_and_audit(session, clock):
    store = SecretStore(session, KEY, clock)
    assert not store.exists("firebase.service_account") and store.get("firebase.service_account") is None
    store.set("firebase.service_account", '{"private_key": "abc"}')
    session.commit()
    value = store.get("firebase.service_account")
    assert isinstance(value, SecretStr) and value.get_secret_value() == '{"private_key": "abc"}'
    assert "abc" not in repr(value) and "abc" not in str(value)
    raw = session.scalars(select(Secret)).one().ciphertext
    assert b"abc" not in raw
    clock.advance(minutes=1)
    store.set("firebase.service_account", SecretStr("new"))
    session.commit()
    assert store.get("firebase.service_account").get_secret_value() == "new"
    events = session.scalars(select(AuditLog).order_by(AuditLog.at)).all()
    assert [e.event for e in events] == ["secret.created", "secret.changed"]
    assert all(e.details == {"name": "firebase.service_account"} for e in events)


def test_copied_row_does_not_decrypt_under_another_name(session, clock):
    store = SecretStore(session, KEY, clock)
    store.set("a.secret", "one")
    store.set("b.secret", "two")
    session.commit()
    a, b = session.scalars(select(Secret).order_by(Secret.name)).all()
    b.ciphertext = a.ciphertext
    session.commit()
    with pytest.raises(crypto.DecryptionError):
        store.get("b.secret")


def test_invalid_name(session, clock):
    with pytest.raises(ValueError):
        SecretStore(session, KEY, clock).set("Bad Name", "x")
