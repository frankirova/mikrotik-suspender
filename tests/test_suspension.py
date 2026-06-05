"""Unit tests for the suspension use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from core.models import SheetEntry, AddressListEntry, SuspensionPreview
from core.interfaces import SheetReader, MikroTikClient
from use_cases.suspension import SuspensionUseCases


# ── Fakes (in-memory implementations for testing) ─────────────

@dataclass
class _FakeSheetReader(SheetReader):
    entries: list[SheetEntry]

    async def read_entries(self) -> list[SheetEntry]:
        return self.entries


class _FakeMikroTik(MikroTikClient):
    def __init__(self) -> None:
        self.address_list: dict[str, list[dict[str, Any]]] = {}
        self.disabled_ids: list[str] = []
        self.comment_updates: list[tuple[str, str]] = []

    async def connect(self, ip: str) -> None:
        if "suspendido" not in self.address_list:
            self.address_list["suspendido"] = []

    async def get_address_list(self, list_name: str) -> list[AddressListEntry]:
        raw = self.address_list.get(list_name, [])
        return [AddressListEntry(id=e["id"], address=e["address"], comment=e["comment"]) for e in raw]

    async def add_address(self, address: str, list_name: str, comment: str) -> None:
        if list_name not in self.address_list:
            self.address_list[list_name] = []
        entry_id = f"id-{address}"
        self.address_list[list_name].append({
            "id": entry_id,
            "address": address,
            "comment": comment,
        })

    async def disable_entry(self, entry_id: str) -> None:
        self.disabled_ids.append(entry_id)

    async def set_comment(self, entry_id: str, comment: str) -> None:
        self.comment_updates.append((entry_id, comment))

    async def disconnect(self) -> None:
        pass


# ── Tests ─────────────────────────────────────────────────────

@pytest.fixture
def sheets() -> _FakeSheetReader:
    return _FakeSheetReader(entries=[
        SheetEntry(ip="10.0.0.1", name="Cliente A"),
        SheetEntry(ip="10.0.0.2", name="Cliente B"),
    ])


@pytest.fixture
def mikrotik() -> _FakeMikroTik:
    mt = _FakeMikroTik()
    mt.address_list["suspendido"] = [
        {"id": "id-10.0.0.1", "address": "10.0.0.1", "comment": "Cliente A"},
    ]
    return mt


@pytest.fixture
def use_cases(sheets, mikrotik) -> SuspensionUseCases:
    return SuspensionUseCases(sheets=sheets, mikrotik=mikrotik)


@pytest.mark.asyncio
async def test_preview_returns_new_and_existing_entries(use_cases):
    result = await use_cases.preview(
        mikrotik_ip="192.168.1.1",
        date="2025-01-15",
    )

    assert isinstance(result, SuspensionPreview)

    # 10.0.0.2 should have been added, so it appears in the list
    matched_ips = [e.address for e in result.current_comments]
    assert "10.0.0.1" in matched_ips
    assert "10.0.0.2" in matched_ips

    # Final comments should have the date appended
    for entry in result.final_comments:
        assert "// SUSPENDIDO - 2025-01-15" in entry.comment


@pytest.mark.asyncio
async def test_execute_disables_and_updates_comments(use_cases, mikrotik):
    await use_cases.execute(
        mikrotik_ip="192.168.1.1",
        date="2025-01-15",
    )

    # Both entries should be disabled
    assert len(mikrotik.disabled_ids) == 2
    assert "id-10.0.0.1" in mikrotik.disabled_ids
    assert "id-10.0.0.2" in mikrotik.disabled_ids

    # Comments should be updated with date
    for entry_id, comment in mikrotik.comment_updates:
        assert "// SUSPENDIDO - 2025-01-15" in comment
