"""Unit tests for the SQLite options repository adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.sqlite_options_repo import SQLiteOptionsRepository


@pytest.mark.asyncio
async def test_add_and_get_all(tmp_path: Path) -> None:
    repo = SQLiteOptionsRepository(path=tmp_path / "options.db")
    try:
        await repo.add("192.168.99.1")
        await repo.add("192.168.99.2")
        result = await repo.get_all()
        assert result == ["192.168.99.1", "192.168.99.2"]
    finally:
        repo.close()


@pytest.mark.asyncio
async def test_add_many_and_get_all(tmp_path: Path) -> None:
    repo = SQLiteOptionsRepository(path=tmp_path / "options.db")
    try:
        await repo.add_many(["192.168.99.1", "192.168.99.2", "192.168.99.3"])
        result = await repo.get_all()
        assert result == ["192.168.99.1", "192.168.99.2", "192.168.99.3"]
    finally:
        repo.close()


@pytest.mark.asyncio
async def test_add_is_idempotent(tmp_path: Path) -> None:
    repo = SQLiteOptionsRepository(path=tmp_path / "options.db")
    try:
        await repo.add("192.168.99.1")
        await repo.add("192.168.99.1")
        await repo.add("192.168.99.1")
        result = await repo.get_all()
        assert result == ["192.168.99.1"]
    finally:
        repo.close()


@pytest.mark.asyncio
async def test_empty_db_returns_empty_list(tmp_path: Path) -> None:
    repo = SQLiteOptionsRepository(path=tmp_path / "options.db")
    try:
        result = await repo.get_all()
        assert result == []
    finally:
        repo.close()


@pytest.mark.asyncio
async def test_schema_version_recorded_on_init(tmp_path: Path) -> None:
    db_path = tmp_path / "options.db"
    repo = SQLiteOptionsRepository(path=db_path)
    try:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 1
        finally:
            conn.close()
    finally:
        repo.close()
