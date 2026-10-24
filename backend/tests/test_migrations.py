"""Migrations up/down on SQLite and MariaDB; models match; upgrades are additive (BUILDPLAN 1.7.7)."""

import ast
import re

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select

from app.db import migrations
from app.db.base import Base
from app.db.models import RevCounter
from app.db.session import make_session_factory

VERSIONS = migrations.BACKEND / "migrations/versions"
DESTRUCTIVE_CALLS = {"drop_table", "drop_column", "drop_constraint", "rename_table", "alter_column"}
DESTRUCTIVE_SQL = re.compile(r"\b(DROP|DELETE|TRUNCATE|RENAME)\b", re.IGNORECASE)
APPROVED = "destructive-approved:"


def run(engine, fn, *args):
    config = migrations.alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        fn(config, *args)


def revisions():
    script = ScriptDirectory.from_config(migrations.alembic_config())
    return [rev.revision for rev in reversed(list(script.walk_revisions()))]


def test_every_migration_up_down_up(bare_engine):
    for revision in revisions():
        run(bare_engine, command.upgrade, revision)
        run(bare_engine, command.downgrade, "-1")
        run(bare_engine, command.upgrade, revision)
        assert migrations.current_revision(bare_engine) == revision
    run(bare_engine, command.downgrade, "base")
    assert set(inspect(bare_engine).get_table_names()) <= {"alembic_version"}


def test_models_match_migrations(engine):
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_rev_counter_seeded(engine):
    with make_session_factory(engine)() as s:
        assert s.scalars(select(RevCounter)).one().id == 1


def _upgrade_body(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")


def destructive_ops(path) -> list[str]:
    source_lines = path.read_text(encoding="utf-8").splitlines()
    found = []
    for node in ast.walk(_upgrade_body(path)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        line = source_lines[node.lineno - 1]
        if APPROVED in line:
            continue
        name = node.func.attr
        sql = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else ""
        if name in DESTRUCTIVE_CALLS or (name == "execute" and isinstance(sql, str) and DESTRUCTIVE_SQL.search(sql)):
            found.append(f"{path.name}:{node.lineno}: {name}")
    return found


def test_upgrades_are_additive():
    """A7: migrations only add, so the previous image keeps running. Destructive steps need
    Martin's approval and a `# destructive-approved: <issue>` comment on the line."""
    problems = [p for path in sorted(VERSIONS.glob("*.py")) for p in destructive_ops(path)]
    assert problems == []


def test_destructive_check_catches_drops(tmp_path):
    sample = tmp_path / "x.py"
    sample.write_text(
        "def upgrade():\n"
        "    op.drop_column('todos', 'note')\n"
        "    with op.batch_alter_table('t') as b:\n"
        "        b.drop_column('a')\n"
        "    op.execute('DELETE FROM todos')\n"
        "    op.drop_table('old')  # destructive-approved: #99\n"
        "    op.add_column('t', None)\n"
        "def downgrade():\n"
        "    op.drop_table('t')\n",
        encoding="utf-8",
    )
    assert sorted(p.split(": ")[1] for p in destructive_ops(sample)) == ["drop_column", "drop_column", "execute"]
