"""Per-database code. The only place with raw SQL (A7, tools/arch_check.py)."""

from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy.engine import make_url

from app.db.dialects import mariadb, sqlite


def is_mariadb(name: str) -> bool:
    return name in ("mysql", "mariadb")


def engine_options(url: str) -> dict:
    backend = make_url(url).get_backend_name()
    if backend == "sqlite":
        return sqlite.engine_options()
    if is_mariadb(backend):
        return mariadb.engine_options()
    raise ValueError(f"unsupported database {backend!r}: use SQLite (dev/tests) or MariaDB")


def configure(engine: Engine) -> None:
    if engine.dialect.name == "sqlite":
        sqlite.configure(engine)
