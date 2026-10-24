"""SQLite specifics: connection pragmas and the cross-process file lock."""

from __future__ import annotations

import fcntl
import os
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, event


def engine_options() -> dict:
    # api and worker run in separate processes in dev; wait instead of failing on a locked DB.
    return {"connect_args": {"timeout": 30, "check_same_thread": False}}


def configure(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        if engine.url.database not in (None, "", ":memory:"):
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


def lock_dir(engine: Engine) -> Path:
    database = engine.url.database
    if database in (None, "", ":memory:"):
        return Path(tempfile.gettempdir()) / f"famapp-locks-{os.getuid()}"
    return Path(f"{os.path.abspath(database)}.locks")


@contextmanager
def file_lock(engine: Engine, name: str, timeout: float) -> Iterator[bool]:
    """Exclusive OS file lock, shared by every process using the same DB file. Yields False on timeout."""
    directory = lock_dir(engine)
    directory.mkdir(parents=True, exist_ok=True)
    fd = os.open(directory / f"{name}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    yield False
                    return
                time.sleep(0.02)
        try:
            yield True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
