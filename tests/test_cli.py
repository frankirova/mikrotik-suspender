"""Tests for the CLI.

Strategy: monkeypatch the use case factory to return a fake, then invoke
the CLI's main() and assert on its exit code and stdout.
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass
from typing import Any

import pytest

from cli import __main__ as cli_main
from core.interfaces import MikroTikClient
from core.models import AddressListEntry, SuspensionPreview
from use_cases.suspension import SuspensionUseCases


# ── Fakes ─────────────────────────────────────────────────────

@dataclass
class _FakeSheetReader:
    entries: list[Any]
    async def read_entries(self) -> list[Any]:
        return self.entries


class _FakeMikroTik(MikroTikClient):
    def __init__(self) -> None:
        self.address_list: dict[str, list[dict[str, Any]]] = {}
        self.executed: bool = False
        self.previewed: bool = False

    async def connect(self, ip: str) -> None:
        if "suspendido" not in self.address_list:
            self.address_list["suspendido"] = []

    async def get_address_list(self, list_name: str) -> list[AddressListEntry]:
        return [
            AddressListEntry(id=e["id"], address=e["address"], comment=e["comment"])
            for e in self.address_list.get(list_name, [])
        ]

    async def add_address(self, address: str, list_name: str, comment: str) -> None:
        self.address_list.setdefault(list_name, []).append({
            "id": f"id-{address}",
            "address": address,
            "comment": comment,
        })

    async def disable_entry(self, entry_id: str) -> None:
        pass

    async def set_comment(self, entry_id: str, comment: str) -> None:
        pass

    async def disconnect(self) -> None:
        pass


@pytest.fixture
def fake_uc(monkeypatch):
    """Replace the use case factory with a fake and return the bound UC."""
    fake_mt = _FakeMikroTik()
    fake_mt.address_list["suspendido"] = [
        {"id": "*1", "address": "10.0.0.1", "comment": "Cliente A"},
    ]
    fake_sheets = _FakeSheetReader(entries=[])  # populated per test if needed

    uc = SuspensionUseCases(sheets=fake_sheets, mikrotik=fake_mt)

    monkeypatch.setattr(cli_main, "get_suspension_use_cases", lambda: uc)
    monkeypatch.setattr(cli_main, "bootstrap", type("B", (), {"run": staticmethod(lambda: None)})())
    return uc, fake_mt


def _invoke(args: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = cli_main.main(args)
        except SystemExit as e:
            # argparse calls sys.exit(2) on error — translate back to a code.
            code = e.code if isinstance(e.code, int) else 1
    return code, out.getvalue(), err.getvalue()


# ── Tests ─────────────────────────────────────────────────────

def test_preview_table_output(fake_uc):
    uc, _ = fake_uc
    # Sheet has an entry that matches the MikroTik address-list entry — that's
    # the case the preview flow needs to render a row.
    from core.models import SheetEntry
    uc._sheets = _FakeSheetReader(entries=[SheetEntry(ip="10.0.0.1", name="Cliente A")])  # type: ignore[attr-defined]
    uc._mikrotik.address_list["suspendido"] = [  # type: ignore[attr-defined]
        {"id": "*1", "address": "10.0.0.1", "comment": "Cliente A"},
    ]
    code, out, err = _invoke(["preview", "--mikrotik", "192.168.1.1", "--date", "2025-01-15"])
    assert code == 0
    assert err == ""
    assert "ID" in out and "CURRENT" in out and "FINAL" in out
    assert "Cliente A" in out
    assert "SUSPENDIDO - 2025-01-15" in out


def test_preview_empty(fake_uc):
    code, out, _ = _invoke(["preview", "--mikrotik", "192.168.1.1"])
    assert code == 0
    assert "(no entries to suspend)" in out


def test_preview_with_json_flag(fake_uc, monkeypatch):
    # The current implementation prints a table. The --json flag is reserved
    # for future machine-readable output; assert it does not error today.
    monkeypatch.setattr(sys, "argv", ["cli"])
    code, _, err = _invoke(["preview", "--mikrotik", "192.168.1.1", "--json"])
    assert code == 0
    assert err == ""


def test_run_executes(fake_uc):
    code, out, _ = _invoke(["run", "--mikrotik", "192.168.1.1", "--date", "2025-01-15"])
    assert code == 0
    assert "OK:" in out
    assert "192.168.1.1" in out
    assert "2025-01-15" in out


def test_missing_required_mikrotik_arg(fake_uc):
    code, _, err = _invoke(["preview"])
    assert code == 2  # argparse's standard error exit code
    assert "required" in err.lower() or "--mikrotik" in err


def test_unknown_subcommand_fails(fake_uc):
    code, _, err = _invoke(["bogus"])
    assert code == 2
    assert "invalid choice" in err.lower()
