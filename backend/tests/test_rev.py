"""next_rev() and stamp() (BUILDPLAN 1.7.1, spec-sync.md section 2)."""

import threading
import time

import pytest
from sqlalchemy import select

from app.db.models import User
from app.db.rev import next_rev, stamp, tombstone
from app.db.session import make_session_factory


def test_next_rev_counts_up(session):
    first = next_rev(session)
    assert [next_rev(session) for _ in range(3)] == [first + 1, first + 2, first + 3]
    session.commit()


def test_rollback_releases_nothing_twice(engine):
    factory = make_session_factory(engine)
    with factory() as s:
        a = next_rev(s)
        s.rollback()
    with factory() as s:
        b = next_rev(s)
        s.commit()
    assert b == a  # a rolled-back rev is reused; only committed revs are visible anyway


def test_stamp_and_tombstone(session, clock):
    user = User(name="A", role="user", time_zone="Europe/Berlin")
    stamp(session, user, clock)
    session.add(user)
    session.commit()
    assert user.created_at == clock.now() == user.updated_at
    first_rev = user.rev
    clock.advance(minutes=5)
    tombstone(session, user, clock)
    session.commit()
    stored = session.scalars(select(User)).one()
    assert stored.deleted_at == clock.now() and stored.rev > first_rev
    assert stored.created_at < stored.updated_at


@pytest.mark.mariadb
def test_commit_order_equals_rev_order(engine, clock):
    """S21: a transaction holding a rev blocks the next one until it commits (MariaDB row lock)."""
    factory = make_session_factory(engine)
    commits: list[tuple[int, float]] = []
    lock = threading.Lock()
    start = threading.Barrier(5)

    def writer(n: int) -> None:
        start.wait()
        with factory() as s:
            user = User(name=f"u{n}", role="user", time_zone="UTC")
            stamp(s, user, clock)
            s.add(user)
            s.flush()
            time.sleep(0.05 * (5 - n))  # earlier revs wait longer before committing
            s.commit()
            with lock:
                commits.append((user.rev, time.monotonic()))

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert len(commits) == 5
    by_rev = sorted(commits)
    assert [c[1] for c in by_rev] == sorted(c[1] for c in commits)
    assert len({c[0] for c in commits}) == 5
