"""Schema state and migrations (decisions section 10, spec-backend-skeleton.md).

A DB revision the code does not know can only be newer (migrations only go forward), so the
previous image accepts it: health is ready and the worker skips the upgrade.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.db.locks import named_lock

log = logging.getLogger(__name__)
BACKEND = Path(__file__).resolve().parents[2]
MIGRATION_LOCK_TIMEOUT = 600


class SchemaState(StrEnum):
    HEAD = "head"
    NEWER = "newer"
    BEHIND = "behind"
    EMPTY = "empty"
    UNREACHABLE = "unreachable"

    @property
    def ready(self) -> bool:
        return self in (SchemaState.HEAD, SchemaState.NEWER)


def alembic_config() -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    return config


def code_revisions() -> tuple[str, set[str]]:
    script = ScriptDirectory.from_config(alembic_config())
    head = script.get_current_head()
    assert head is not None, "no migrations"
    return head, {rev.revision for rev in script.walk_revisions()}


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def schema_state(engine: Engine) -> SchemaState:
    try:
        current = current_revision(engine)
    except SQLAlchemyError:
        return SchemaState.UNREACHABLE
    if current is None:
        return SchemaState.EMPTY
    head, known = code_revisions()
    if current == head:
        return SchemaState.HEAD
    return SchemaState.BEHIND if current in known else SchemaState.NEWER


def upgrade(engine: Engine) -> SchemaState:
    """Worker start: migrate to head under the DB lock, unless the DB is newer than the code."""
    with named_lock(engine, "migrations", timeout=MIGRATION_LOCK_TIMEOUT):
        state = schema_state(engine)
        if state == SchemaState.NEWER:
            log.warning(
                "database schema is newer than this code; skipping migrations",
                extra={"db_revision": current_revision(engine)},
            )
            return state
        if state != SchemaState.HEAD:
            config = alembic_config()
            with engine.begin() as conn:
                config.attributes["connection"] = conn
                command.upgrade(config, "head")
            log.info("migrated database", extra={"db_revision": current_revision(engine)})
        return schema_state(engine)
