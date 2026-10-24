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
from app.clock import FakeClock
from app.db.base import Base
from app.db.dialects import is_mariadb
from app.db.session import make_engine, make_session_factory
from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

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


@pytest.fixture
def engine(database_url) -> Iterator[Engine]:
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        if MARIADB_URL:
            Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with make_session_factory(engine)() as session:
        yield session
