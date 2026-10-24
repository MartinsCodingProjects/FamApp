"""Shared fixtures (BUILDPLAN 1.3.3, 1.3.6).

Database: a fresh SQLite file per test by default. With DATABASE_URL pointing at MariaDB
(CI job backend-mariadb) the same tests run against it, and tests marked `mariadb` run too;
without MariaDB they are skipped.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, MetaData
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.clock import FakeClock
from app.config import load_settings
from app.db.base import Base
from app.db.dialects import is_mariadb
from app.db.session import make_engine, make_session_factory

# A fixed, unremarkable instant; tests move it with clock.set()/clock.advance().
DEFAULT_NOW = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)


def _mariadb_url() -> str | None:
    url = os.environ.get("DATABASE_URL")
    if url and is_mariadb(make_url(url).get_backend_name()):
        return url
    return None


MARIADB_URL = _mariadb_url()


def pytest_collection_modifyitems(config, items) -> None:
    if MARIADB_URL:
        return
    skip = pytest.mark.skip(reason="needs MariaDB (DATABASE_URL=mysql+pymysql://...)")
    for item in items:
        if "mariadb" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(DEFAULT_NOW)


@pytest.fixture
def database_url(tmp_path) -> str:
    return MARIADB_URL or f"sqlite:///{tmp_path / 'test.db'}"


def _drop_everything(engine: Engine) -> None:
    """MariaDB is shared by all tests: remove every table, incl. alembic_version."""
    metadata = MetaData()
    metadata.reflect(engine)
    metadata.drop_all(engine)


@pytest.fixture
def bare_engine(database_url) -> Iterator[Engine]:
    """An engine on an empty database (no tables)."""
    engine = make_engine(database_url)
    if MARIADB_URL:
        _drop_everything(engine)
    try:
        yield engine
    finally:
        if MARIADB_URL:
            _drop_everything(engine)
        engine.dispose()


@pytest.fixture
def engine(bare_engine) -> Engine:
    Base.metadata.create_all(bare_engine)
    return bare_engine


TEST_MASTER_KEY = "dGVzdC1tYXN0ZXIta2V5LTMyLWJ5dGVzLWxvbmchISE="  # base64 of 32 bytes, tests only


@pytest.fixture
def prod_settings(database_url):
    """Production-like settings (FAMAPP_DEV off) with test values."""
    return load_settings(
        dev=False,
        database_url=database_url,
        master_key=TEST_MASTER_KEY,
        setup_token="t" * 40,
        cf_access_team_domain="famapp-test.cloudflareaccess.com",
        cf_access_aud="test-aud",
    )


@pytest.fixture
def dev_settings(database_url):
    return load_settings(dev=True, database_url=database_url)


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with make_session_factory(engine)() as session:
        yield session
