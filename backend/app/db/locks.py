"""Named locks across processes (A7): worker jobs, migrations, pairing codes.

SQLite: an OS file lock next to the DB file. MariaDB: GET_LOCK. Use only this module.

    with named_lock(engine, "migrations", timeout=30):
        ...
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine

from app.db.dialects import is_mariadb, mariadb, sqlite

LOCK_NAME = re.compile(r"^[a-z0-9_.:-]{1,48}$")
PREFIX = "famapp:"


class LockTimeout(Exception):
    pass


@contextmanager
def named_lock(engine: Engine, name: str, timeout: float = 10.0) -> Iterator[None]:
    """Hold the lock `name` for the block; raise LockTimeout if it is not free within `timeout` seconds."""
    if not LOCK_NAME.match(name):
        raise ValueError(f"invalid lock name {name!r} (lowercase, digits, _.:-, at most 48 characters)")
    if engine.dialect.name == "sqlite":
        manager = sqlite.file_lock(engine, name, timeout)
    elif is_mariadb(engine.dialect.name):
        manager = mariadb.get_lock(engine, PREFIX + name, timeout)
    else:
        raise ValueError(f"no lock implementation for {engine.dialect.name!r}")
    with manager as acquired:
        if not acquired:
            raise LockTimeout(f"lock {name!r} not acquired within {timeout} s")
        yield
