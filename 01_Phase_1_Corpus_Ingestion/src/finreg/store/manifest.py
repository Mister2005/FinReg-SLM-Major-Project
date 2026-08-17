from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_MIGRATION_NAME_RE = re.compile(r"^(\d{4})_.*\.sql$")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _discover_migrations() -> list[tuple[int, Path]]:
    migrations: list[tuple[int, Path]] = []
    for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        match = _MIGRATION_NAME_RE.match(path.name)
        if not match:
            continue
        migrations.append((int(match.group(1)), path))
    return sorted(migrations, key=lambda item: item[0])


def current_schema_version(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if cursor.fetchone() is None:
        return 0
    row = conn.execute(
        "SELECT MAX(version) AS version FROM schema_version"
    ).fetchone()
    return row["version"] if row["version"] is not None else 0


def migrate(conn: sqlite3.Connection) -> int:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER NOT NULL,
            applied_at  TEXT    NOT NULL
        )
        """
    )
    conn.commit()

    applied = current_schema_version(conn)
    for version, path in _discover_migrations():
        if version <= applied:
            continue
        sql = path.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, _utcnow_iso()),
        )
        conn.commit()
        applied = version
    return applied


def open_manifest(db_path: Path) -> sqlite3.Connection:
    conn = connect(db_path)
    migrate(conn)
    return conn
