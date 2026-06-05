"""SQLite adapter — persists option IPs via the OptionsRepository port.

Schema is auto-created on first use with a `PRAGMA user_version`-style
version table for future migrations. All writes use `INSERT OR IGNORE`,
so adding the same IP twice is a no-op.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from core.interfaces import OptionsRepository
from core.config import config

logger = logging.getLogger(__name__)


SCHEMA_VERSION = 1

INIT_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS options (
    option TEXT PRIMARY KEY
);
"""


class SQLiteOptionsRepository(OptionsRepository):
    """Stores option IPs in a local SQLite database with auto-migration."""

    def __init__(self, path: Path | None = None) -> None:
        self._path: Path = path or config.options_db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path))
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript(INIT_SQL)
        cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
        if cur.fetchone() is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            conn.commit()
            logger.info("SQLite schema initialised at version %d", SCHEMA_VERSION)

    async def add(self, option: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("INSERT OR IGNORE INTO options (option) VALUES (?)", (option,))
            conn.commit()

    async def add_many(self, options: list[str]) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.executemany(
                "INSERT OR IGNORE INTO options (option) VALUES (?)",
                [(opt,) for opt in options],
            )
            conn.commit()

    async def get_all(self) -> list[str]:
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute("SELECT option FROM options ORDER BY option")
            return [row[0] for row in cur.fetchall()]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
