"""Alembic environment. render_as_batch=True so SQLite can ALTER (A7)."""

from alembic import context

from app.db.base import Base
from app.db.session import make_engine

config = context.config
target_metadata = Base.metadata


def run_migrations() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = make_engine(config.get_main_option("sqlalchemy.url") or None)
    with engine.connect() as connection:
        _run(connection)
    engine.dispose()


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("offline migrations are not used")
run_migrations()
