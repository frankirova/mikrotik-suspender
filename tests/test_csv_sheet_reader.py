"""Unit tests for the CSV sheet reader adapter."""
from __future__ import annotations

from pathlib import Path

import pytest

from adapters.csv_sheet_reader import CSVSheetReader


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


@pytest.mark.asyncio
async def test_reads_valid_csv(tmp_path: Path) -> None:
    csv = tmp_path / "clientes.csv"
    _write_csv(csv, "ip,nombre\n192.168.88.10,Alice\n192.168.88.11,Bob\n")

    reader = CSVSheetReader()
    entries = await reader.read_entries(str(csv))

    assert len(entries) == 2
    assert entries[0].ip == "192.168.88.10"
    assert entries[0].name == "Alice"
    assert entries[1].ip == "192.168.88.11"
    assert entries[1].name == "Bob"


@pytest.mark.asyncio
async def test_returns_empty_when_file_missing(tmp_path: Path) -> None:
    reader = CSVSheetReader()
    entries = await reader.read_entries(str(tmp_path / "does-not-exist.csv"))
    assert entries == []


@pytest.mark.asyncio
async def test_returns_empty_for_empty_file(tmp_path: Path) -> None:
    csv = tmp_path / "empty.csv"
    _write_csv(csv, "")

    reader = CSVSheetReader()
    entries = await reader.read_entries(str(csv))
    assert entries == []


@pytest.mark.asyncio
async def test_raises_when_required_headers_missing(tmp_path: Path) -> None:
    csv = tmp_path / "bad.csv"
    _write_csv(csv, "ip,cliente\n192.168.88.10,Alice\n")

    reader = CSVSheetReader()
    with pytest.raises(ValueError, match="missing required headers"):
        await reader.read_entries(str(csv))


@pytest.mark.asyncio
async def test_skips_blank_ip_rows(tmp_path: Path) -> None:
    csv = tmp_path / "clientes.csv"
    _write_csv(csv, "ip,nombre\n192.168.88.10,Alice\n,Orphan\n192.168.88.11,Bob\n")

    reader = CSVSheetReader()
    entries = await reader.read_entries(str(csv))

    assert len(entries) == 2
    assert [e.ip for e in entries] == ["192.168.88.10", "192.168.88.11"]


@pytest.mark.asyncio
async def test_mtime_cache_hits_when_unchanged(tmp_path: Path) -> None:
    """The cache should be primed after a read and serve subsequent calls."""
    csv = tmp_path / "clientes.csv"
    _write_csv(csv, "ip,nombre\n192.168.88.10,Alice\n")

    reader = CSVSheetReader()
    first = await reader.read_entries(str(csv))
    # The internal cache is populated after the first read.
    assert reader._cached_entries == first
    assert reader._cached_path == csv
    assert reader._cached_mtime == csv.stat().st_mtime

    # A second read with no file change returns the same cached list.
    second = await reader.read_entries(str(csv))
    assert first == second


@pytest.mark.asyncio
async def test_mtime_cache_invalidates_on_change(tmp_path: Path) -> None:
    """When the file's mtime changes, the cache should be re-read."""
    csv = tmp_path / "clientes.csv"
    _write_csv(csv, "ip,nombre\n192.168.88.10,Alice\n")

    reader = CSVSheetReader()
    await reader.read_entries(str(csv))

    # Rewrite the file — mtime will be newer (or same second, but content differs).
    _write_csv(csv, "ip,nombre\n192.168.88.10,AliceRenamed\n")
    # Force a newer mtime so the cache miss is guaranteed even on coarse filesystems.
    import os
    new_mtime = csv.stat().st_mtime + 5
    os.utime(csv, (new_mtime, new_mtime))

    entries = await reader.read_entries(str(csv))
    assert entries[0].name == "AliceRenamed"
