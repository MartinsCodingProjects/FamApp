"""Sync revisions (README 6, A7). Use only next_rev() / stamp(), never set `rev` by hand.

next_rev() must run inside the transaction that writes the row: the counter row stays locked
until that transaction commits, so a row with a lower rev can never become visible after a
delta has already returned a higher one (spec-sync.md section 2).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.clock import Clock
from app.db.dialects import is_mariadb, mariadb, sqlite


def next_rev(session: Session) -> int:
    name = session.get_bind().dialect.name
    if name == "sqlite":
        return sqlite.next_rev(session)
    if is_mariadb(name):
        return mariadb.next_rev(session)
    raise ValueError(f"no next_rev() for {name!r}")


def stamp(session: Session, row, clock: Clock) -> None:
    """Give a synced row a new rev and its timestamps; call for every insert and update."""
    now = clock.now()
    if row.created_at is None:
        row.created_at = now
    row.updated_at = now
    row.rev = next_rev(session)


def tombstone(session: Session, row, clock: Clock) -> None:
    """Delete a synced row by tombstone (clients learn about it through the delta)."""
    row.deleted_at = clock.now()
    stamp(session, row, clock)
