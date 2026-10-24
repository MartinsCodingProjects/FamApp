"""Named locks (BUILDPLAN 1.3.5, 1.3.10): exclusive across connections and processes."""

import multiprocessing
import threading

import pytest

from app.db.locks import LockTimeout, named_lock
from app.db.session import make_engine


def _hold_lock(url: str, name: str, ready, release) -> None:
    engine = make_engine(url)
    with named_lock(engine, name, timeout=5):
        ready.set()
        release.wait(10)
    engine.dispose()


def test_lock_is_reentrant_after_release(engine):
    with named_lock(engine, "jobs.watchdog", timeout=1):
        pass
    with named_lock(engine, "jobs.watchdog", timeout=1):
        pass


def test_different_names_do_not_block(engine):
    with named_lock(engine, "a", timeout=1), named_lock(engine, "b", timeout=1):
        pass


def test_invalid_name(engine):
    with pytest.raises(ValueError), named_lock(engine, "Has Spaces"):
        pass


def test_lock_excludes_other_process(database_url):
    """api and worker are separate processes; the lock must hold across them (file lock on SQLite)."""
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    holder = ctx.Process(target=_hold_lock, args=(database_url, "migrations", ready, release))
    holder.start()
    try:
        assert ready.wait(30)
        engine = make_engine(database_url)
        with pytest.raises(LockTimeout), named_lock(engine, "migrations", timeout=0.2):
            pass
        release.set()
        holder.join(10)
        with named_lock(engine, "migrations", timeout=5):
            pass
        engine.dispose()
    finally:
        release.set()
        holder.join(10)


@pytest.mark.mariadb
def test_get_lock_excludes_concurrent_connections(engine):
    """GET_LOCK is per connection: two threads with their own connections exclude each other."""
    inside = []
    errors = []
    start = threading.Barrier(4)

    def worker(n: int) -> None:
        start.wait()
        try:
            with named_lock(engine, "concurrency", timeout=10):
                inside.append(n)
                assert len(inside) == 1, "two holders at once"
                threading.Event().wait(0.1)
                inside.remove(n)
        except AssertionError as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert errors == []
