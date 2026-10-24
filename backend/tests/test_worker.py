"""Worker start: migrations under the lock, newer schema skipped, clean stop (BUILDPLAN 1.4.6)."""

import logging
import threading

from app.db import migrations
from app.db.migrations import SchemaState
from sqlalchemy import MetaData, Table

from app import worker


def test_worker_migrates_then_stops(dev_settings, bare_engine):
    stop = threading.Event()
    started = threading.Event()
    real_make = worker.make_scheduler

    def make_scheduler():
        scheduler = real_make()
        original_start = scheduler.start

        def start(*args, **kwargs):
            original_start(*args, **kwargs)
            started.set()

        scheduler.start = start
        return scheduler

    worker.make_scheduler = make_scheduler
    try:
        thread = threading.Thread(target=lambda: worker.run(dev_settings, stop))
        thread.start()
        assert started.wait(30)
        assert migrations.schema_state(bare_engine) == SchemaState.HEAD
        stop.set()
        thread.join(30)
        assert not thread.is_alive()
    finally:
        worker.make_scheduler = real_make


def test_older_code_starts_against_newer_schema(bare_engine, caplog):
    migrations.upgrade(bare_engine)
    table = Table("alembic_version", MetaData(), autoload_with=bare_engine)
    with bare_engine.begin() as conn:
        conn.execute(table.update().values(version_num="f00dfeedcafe"))
    caplog.set_level(logging.WARNING, logger="app.db.migrations")
    assert migrations.upgrade(bare_engine) == SchemaState.NEWER
    assert migrations.current_revision(bare_engine) == "f00dfeedcafe"  # untouched
    assert any("newer than this code" in r.getMessage() for r in caplog.records)


def test_two_workers_starting_at_once(bare_engine):
    results = []
    threads = [threading.Thread(target=lambda: results.append(migrations.upgrade(bare_engine))) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert results == [SchemaState.HEAD, SchemaState.HEAD]


def test_migrations_run_down_and_up(bare_engine):
    from alembic import command

    migrations.upgrade(bare_engine)
    config = migrations.alembic_config()
    with bare_engine.begin() as conn:
        config.attributes["connection"] = conn
        command.downgrade(config, "base")
    assert migrations.schema_state(bare_engine) == SchemaState.EMPTY
    assert migrations.upgrade(bare_engine) == SchemaState.HEAD
