"""Factory functions that wire concrete adapters into use cases.

This is the Composition Root — the only place where concrete classes
are instantiated and wired together.
"""

from __future__ import annotations

from adapters.csv_sheet_reader import CSVSheetReader
from adapters.mikrotik_adapter import RouterOSClient
from adapters.sqlite_options_repo import SQLiteOptionsRepository
from core.config import AppConfig, RouterConfig
from use_cases.options_mgmt import OptionsUseCases
from use_cases.suspension import SuspensionUseCases

# ── Suspension ────────────────────────────────────────────────


def get_suspension_use_cases() -> SuspensionUseCases:
    """Build a fully-wired SuspensionUseCases instance."""
    app_config = AppConfig()
    router_config = RouterConfig()
    return SuspensionUseCases(
        sheets=CSVSheetReader(app_config.csv_path),
        mikrotik=RouterOSClient(router_config),
        targets=router_config.routers,
        max_entries=app_config.max_entries,
    )


# ── Options ───────────────────────────────────────────────────


def get_options_use_cases() -> OptionsUseCases:
    """Build a fully-wired OptionsUseCases instance."""
    return OptionsUseCases(repo=SQLiteOptionsRepository())
