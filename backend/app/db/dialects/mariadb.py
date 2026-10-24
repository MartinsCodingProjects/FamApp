"""MariaDB specifics: engine options and GET_LOCK named locks."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session


def engine_options() -> dict:
    return {"pool_pre_ping": True, "pool_recycle": 3600, "connect_args": {"charset": "utf8mb4"}}


@contextmanager
def get_lock(engine: Engine, name: str, timeout: float) -> Iterator[bool]:
    """GET_LOCK on a dedicated connection, held until the block ends. Yields False on timeout."""
    with engine.connect() as conn:
        # GET_LOCK takes whole seconds; round up so a short timeout still waits.
        acquired = conn.execute(text("SELECT GET_LOCK(:name, :timeout)"), {"name": name, "timeout": math.ceil(timeout)})
        if acquired.scalar() != 1:
            yield False
            return
        try:
            yield True
        finally:
            conn.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})


def next_rev(session: Session) -> int:
    # The UPDATE row-locks the counter until commit, so commit order equals rev order (A7, 1.7.1).
    session.execute(text("UPDATE rev_counter SET value = LAST_INSERT_ID(value + 1) WHERE id = 1"))
    return session.execute(text("SELECT LAST_INSERT_ID()")).scalar_one()
