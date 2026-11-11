"""Use cases for the IP suspension workflow.

Holds the business logic that was previously scattered across
routes.py and mikrotik.py, without any framework or transport dependency.
"""

from __future__ import annotations

from core.config import config
from core.models import SheetEntry, AddressListEntry, SuspensionPreview
from core.interfaces import SheetReader, MikroTikClient

SUSPEND_LIST = "suspendido"  # fallback when neither the run nor the config picks one


def _resolve_list_name(list_name: str | None) -> str:
    """A per-run name wins; empty falls back to LIST_NAME from the environment."""
    return (list_name or "").strip() or config.list_name


def _build_comment_map(
    sheet_entries: list[SheetEntry],
    mkt_entries: list[AddressListEntry],
    date: str,
) -> tuple[list[AddressListEntry], list[AddressListEntry]]:
    """Cross-reference sheet entries with MikroTik address-list entries.

    Returns (matched_entries, final_comments) for all IPs found in both sources.
    - matched_entries: entries as they currently are in MikroTik.
    - final_comments:   same entries with the suspension date appended to their comment.
    """
    sheet_by_ip = {e.ip: e for e in sheet_entries}

    matched: list[AddressListEntry] = []
    for mkt in mkt_entries:
        if mkt.address in sheet_by_ip:
            matched.append(mkt)

    final: list[AddressListEntry] = []
    for entry in matched:
        final.append(
            AddressListEntry(
                id=entry.id,
                address=entry.address,
                comment=f"{entry.comment}// SUSPENDIDO - {date}",
            )
        )

    return matched, final


def _project_pending_entries(
    sheet_entries: list[SheetEntry],
    mkt_entries: list[AddressListEntry],
) -> list[AddressListEntry]:
    """Entries a run would create, without creating them.

The preview must not touch the router: on a real RouterOS a new address-list
entry is created with `disabled=false`, so syncing during a preview would
already apply the block. Pending entries are projected with an empty id, which
the API surfaces as "not created yet".
    """
    existing_ips = {e.address for e in mkt_entries}
    pending = [
        AddressListEntry(id="", address=entry.ip, comment=entry.name)
        for entry in sheet_entries
        if entry.ip not in existing_ips
    ]
    return list(mkt_entries) + pending


class SuspensionUseCases:
    """Orchestrates the preview + execute flows."""

    def __init__(self, sheets: SheetReader, mikrotik: MikroTikClient) -> None:
        self._sheets = sheets
        self._mikrotik = mikrotik

    async def _sync_new_entries(
        self,
        sheet_entries: list[SheetEntry],
        mkt_entries: list[AddressListEntry],
        list_name: str,
    ) -> list[AddressListEntry]:
        """Add IPs that are in the sheet but not yet in the MikroTik list."""
        existing_ips = {e.address for e in mkt_entries}
        for entry in sheet_entries:
            if entry.ip not in existing_ips:
                await self._mikrotik.add_address(entry.ip, list_name, entry.name)

        # Return the refreshed list after addition
        return await self._mikrotik.get_address_list(list_name)

    async def preview(
        self,
        mikrotik_ip: str,
        date: str,
        user: str,
        password: str,
        list_name: str | None = None,
    ) -> SuspensionPreview:
        """Preview what would be suspended. Read-only: the router is never written."""
        name = _resolve_list_name(list_name)
        sheet_entries = await self._sheets.read_entries()
        await self._mikrotik.connect(mikrotik_ip, user, password)

        current_list = await self._mikrotik.get_address_list(name)
        referenced = await self._mikrotik.get_referenced_lists()
        projected_list = _project_pending_entries(sheet_entries, current_list)

        matched, final = _build_comment_map(sheet_entries, projected_list, date)

        await self._mikrotik.disconnect()
        return SuspensionPreview(
            current_comments=matched,
            final_comments=final,
            list_name=name,
            list_has_entries=bool(current_list),
            referenced_by_rules=name in referenced,
        )

    async def execute(
        self,
        mikrotik_ip: str,
        date: str,
        user: str,
        password: str,
        list_name: str | None = None,
    ) -> None:
        """Execute the suspension: sync, disable entries, and update comments."""
        name = _resolve_list_name(list_name)
        sheet_entries = await self._sheets.read_entries()
        await self._mikrotik.connect(mikrotik_ip, user, password)

        current_list = await self._mikrotik.get_address_list(name)
        updated_list = await self._sync_new_entries(sheet_entries, current_list, name)

        matched, final = _build_comment_map(sheet_entries, updated_list, date)

        for entry in matched:
            await self._mikrotik.disable_entry(entry.id)

        for entry in final:
            await self._mikrotik.set_comment(entry.id, entry.comment)

        await self._mikrotik.disconnect()
