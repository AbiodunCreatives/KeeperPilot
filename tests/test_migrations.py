"""Migration tests: alembic upgrade/downgrade lifecycle against a temp SQLite DB.

These tests run synchronously because alembic's env.py drives the async engine
via ``asyncio.run()``, which cannot nest inside a running event loop.
"""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_INI = PROJECT_ROOT / "database" / "alembic.ini"

EXPECTED_TABLES = {
    "users",
    "wallets",
    "user_preferences",
    "positions",
    "executions",
    "audit_logs",
}


def _config(tmp_path: Path) -> Config:
    config = Config(str(MIGRATIONS_INI))
    config.set_main_option("script_location", str(MIGRATIONS_INI.parent / "migrations"))
    return config


def _table_names(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()


def test_upgrade_to_head_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "migrate.db"
    config = _config(tmp_path)
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path.as_posix()}")

    command.upgrade(config, "head")

    assert EXPECTED_TABLES <= _table_names(db_path)


def test_upgrade_then_downgrade_is_reversible(tmp_path: Path) -> None:
    db_path = tmp_path / "migrate.db"
    config = _config(tmp_path)
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path.as_posix()}")

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    assert _table_names(db_path) == {"alembic_version"}
