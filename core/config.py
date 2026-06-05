"""Centralised configuration — loads everything from environment variables once.

Eliminates the scattered load_dotenv() calls throughout the original codebase.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _required(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable: {key}. "
            f"Set it in your .env file or environment."
        )
    return val


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _expand_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


@dataclass(frozen=True)
class AppConfig:
    # ── MikroTik ──────────────────────────────────────────────
    mikrotik_user: str = field(default_factory=lambda: _required("USER_MIKROTIK"))
    mikrotik_password: str = field(default_factory=lambda: _required("PASS_MIKROTIK"))

    # ── Data (replaces Google Sheets + MongoDB) ───────────────
    data_dir: Path = field(default_factory=lambda: _expand_path(_optional("DATA_DIR", "./data")))
    csv_path: Path = field(default_factory=lambda: _expand_path(_optional("CSV_PATH", "./data/clientes.csv")))
    options_db_path: Path = field(default_factory=lambda: _expand_path(_optional("OPTIONS_DB_PATH", "./data/options.db")))

    # ── CORS ──────────────────────────────────────────────────
    cors_origins: list[str] = field(default_factory=lambda: [
        _optional("CORS_ORIGIN_1", "http://localhost:5173"),
        _optional("CORS_ORIGIN_2", "http://localhost:8000"),
    ])

    # ── Server ────────────────────────────────────────────────
    host: str = field(default_factory=lambda: _optional("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_optional("PORT", "8000")))

    # ── Authentication (optional) ─────────────────────────────
    # When set, all sensitive endpoints require `Authorization: Bearer <api_key>`.
    # When unset (default), authentication is disabled and a WARNING is logged
    # at startup — intended for local development only.
    api_key: str | None = field(default_factory=lambda: _optional("API_KEY") or None)


# Single instance — import this everywhere instead of building your own.
config = AppConfig()
