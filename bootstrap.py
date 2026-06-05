"""Bootstrap — creates data files and seeds the DB on app startup.

Idempotent: safe to run multiple times. If `data/clientes.csv` is missing,
it is copied from the bundled `data/clientes.csv.example`. If the SQLite
database is missing, it is created with the current schema and seeded with
`DEFAULT_OPTIONS`.
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
from pathlib import Path

from core.config import config

logger = logging.getLogger(__name__)


SAMPLE_CSV = Path(__file__).parent / "data" / "clientes.csv.example"


DEFAULT_OPTIONS: list[str] = [
    "192.168.2.238",
    "192.168.99.1",
    "192.168.99.2",
    "192.168.99.3",
    "192.168.99.4",
    "192.168.99.5",
    "192.168.99.6",
    "192.168.99.7",
    "192.168.99.8",
    "192.168.99.9",
    "192.168.99.10",
]


SCHEMA_VERSION = 1

INIT_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS options (
    option TEXT PRIMARY KEY
);
"""


def ensure_csv_file() -> None:
    """Create the runtime CSV from the example if it doesn't exist yet."""
    config.csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not config.csv_path.exists():
        if SAMPLE_CSV.exists():
            shutil.copy2(SAMPLE_CSV, config.csv_path)
            logger.info("Seeded sample CSV at %s", config.csv_path)
        else:
            config.csv_path.touch()
            logger.warning("No sample CSV found — created empty file at %s", config.csv_path)


def ensure_db() -> None:
    """Create the SQLite DB, run migrations, and seed default options if empty."""
    config.options_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.options_db_path))
    try:
        conn.executescript(INIT_SQL)
        cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
        if cur.fetchone() is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            conn.commit()
            logger.info("SQLite schema initialised at version %d", SCHEMA_VERSION)

        cur = conn.execute("SELECT COUNT(*) FROM options")
        count = cur.fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO options (option) VALUES (?)",
                [(opt,) for opt in DEFAULT_OPTIONS],
            )
            conn.commit()
            logger.info("Seeded %d default options into %s", len(DEFAULT_OPTIONS), config.options_db_path)
    finally:
        conn.close()


def run() -> None:
    """Run all bootstrap steps. Called once on app startup."""
    logger.info("Bootstrapping data dir at %s", config.data_dir)
    ensure_csv_file()
    ensure_db()
    logger.info("Bootstrap complete")
