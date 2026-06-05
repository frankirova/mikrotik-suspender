"""Factory functions that wire concrete adapters into use cases.

This is the Composition Root — the only place where concrete classes
are instantiated and wired together.
"""

from __future__ import annotations

from adapters.csv_sheet_reader import CSVSheetReader
from adapters.mikrotik_adapter import RouterOSClient
from adapters.sqlite_options_repo import SQLiteOptionsRepository
from use_cases.suspension import SuspensionUseCases
from use_cases.options_mgmt import OptionsUseCases


# ── Suspension ────────────────────────────────────────────────

def get_suspension_use_cases() -> SuspensionUseCases:
    """Build a fully-wired SuspensionUseCases instance."""
    return SuspensionUseCases(
        sheets=CSVSheetReader(),
        mikrotik=RouterOSClient(),
    )


# ── Options ───────────────────────────────────────────────────

def get_options_use_cases() -> OptionsUseCases:
    """Build a fully-wired OptionsUseCases instance."""
    return OptionsUseCases(repo=SQLiteOptionsRepository())
