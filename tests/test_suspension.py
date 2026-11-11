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


@pytest.mark.asyncio
async def test_preview_does_not_write_to_the_router(use_cases, mikrotik):
    """A preview must be read-only: no new entries, no disables, no comments."""
    before = [dict(entry) for entry in mikrotik.address_list["suspendido"]]

    result = await use_cases.preview(
        mikrotik_ip="192.168.1.1",
        date="2025-01-15",
    )

    # The router is untouched: the pending IP was projected, not added.
    assert mikrotik.address_list["suspendido"] == before
    assert mikrotik.disabled_ids == []
    assert mikrotik.comment_updates == []

    # The operator still sees what a run would do, including the pending IP.
    assert [e.address for e in result.current_comments] == ["10.0.0.1", "10.0.0.2"]
    assert result.current_comments[0].id == "id-10.0.0.1"
    assert result.current_comments[1].id == ""  # not created yet
    assert result.final_comments[0].comment == "Cliente A// SUSPENDIDO - 2025-01-15"
    assert result.final_comments[1].comment == "Cliente B// SUSPENDIDO - 2025-01-15"


@pytest.mark.asyncio
async def test_uses_the_given_list_name(use_cases, mikrotik):
    """The address-list name is configurable per run."""
    await use_cases.execute(
        mikrotik_ip="192.168.1.1",
        date="2025-01-15",
        list_name="morosos",
    )

    # The target list starts empty, so both clients are added there.
    assert [e["address"] for e in mikrotik.address_list["morosos"]] == ["10.0.0.1", "10.0.0.2"]
    # The default list is left untouched.
    assert [e["address"] for e in mikrotik.address_list["suspendido"]] == ["10.0.0.1"]


@pytest.mark.asyncio
async def test_list_name_defaults_to_config(use_cases, mikrotik, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr("use_cases.suspension.config", SimpleNamespace(list_name="morosos"))

    result = await use_cases.preview(mikrotik_ip="192.168.1.1", date="2025-01-15")

    assert result.list_name == "morosos"
    # "morosos" does not exist yet, so both clients are projected as pending.
    assert [e.id for e in result.current_comments] == ["", ""]
