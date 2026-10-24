from pathlib import Path

import arch_check
import pytest
from conftest import REPO


def write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_repo_passes():
    assert arch_check.main(["--root", str(REPO)]) == 0


@pytest.mark.parametrize(
    ("rel", "content", "rule"),
    [
        ("backend/app/sync/delta.py", 'session.execute(text("SELECT * FROM todos"))\n', "raw-sql"),
        ("backend/app/sync/delta.py", 'conn.exec_driver_sql("PRAGMA foreign_keys=ON")\n', "raw-sql"),
        ("backend/app/sync/delta.py", 'cursor.execute("""\n', None),
        ("backend/migrations/versions/x.py", 'op.execute("UPDATE todos SET rev = 0")\n', "raw-sql"),
        ("backend/app/domain/levels.py", "now = datetime.now(UTC)\n", "clock"),
        ("backend/app/domain/levels.py", "today = date.today()\n", "clock"),
        ("backend/app/jobs/watchdog.py", "started = time.time()\n", "clock"),
        ("app/modules/famapp-engine/engine-core/src/main/kotlin/Planner.kt", "val now = Instant.now()\n", "clock"),
        ("app/modules/famapp-engine/engine-android/src/main/A.kt", "val t = System.currentTimeMillis()\n", "clock"),
        ("app/screens/Todos.tsx", 'import * as SQLite from "expo-sqlite";\n', "js-db"),
        ("app/screens/Todos.tsx", 'import AsyncStorage from "@react-native-async-storage/async-storage";\n', "js-db"),
        ("app/screens/Todos.tsx", 'import { Engine } from "../modules/famapp-engine";\n', "js-engine"),
    ],
)
def test_violations_fail(tmp_path, rel, content, rule):
    write(tmp_path, rel, content)
    errors = arch_check.run(tmp_path)
    if rule is None:
        assert errors == []
    else:
        assert len(errors) == 1 and f"[{rule}]" in errors[0] and errors[0].startswith(f"{rel}:1:")


@pytest.mark.parametrize(
    ("rel", "content"),
    [
        ("backend/app/db/dialects/sqlite.py", 'conn.execute(text("UPDATE rev_counter SET value = value + 1"))\n'),
        ("backend/app/clock.py", "return datetime.now(UTC)\n"),
        ("backend/tests/test_levels.py", "now = datetime.now(UTC)\n"),
        ("backend/app/domain/levels.py", "now = clock.now()\n# datetime.now() is forbidden here\n"),
        ("backend/app/domain/levels.py", "x = datetime.now(UTC)  # arch-ignore: log timestamp only\n"),
        ("backend/app/domain/levels.py", 'stmt = select(Todo).where(Todo.title == "SELECT")\n'),
        ("app/modules/famapp-engine/engine-core/src/main/kotlin/SystemClock.kt", "Instant.now()\n"),
        ("app/modules/famapp-engine/engine-core/src/test/kotlin/PlannerTest.kt", "Instant.now()\n"),
        ("app/data/repo.native.ts", 'import { Engine } from "../modules/famapp-engine";\n'),
        ("app/modules/famapp-engine/index.ts", 'export * from "./src/famapp-engine";\n'),
        ("app/screens/Todos.tsx", 'import { listTodos } from "../data/repo";\n'),
    ],
)
def test_allowed(tmp_path, rel, content):
    write(tmp_path, rel, content)
    assert arch_check.run(tmp_path) == []


def test_main_exit_code(tmp_path):
    write(tmp_path, "backend/app/x.py", "datetime.utcnow()\n")
    assert arch_check.main(["--root", str(tmp_path)]) == 1
