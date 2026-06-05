"""Use cases for the IP suspension workflow.

Holds the business logic that was previously scattered across
routes.py and mikrotik.py, without any framework or transport dependency.
"""

from __future__ import annotations

from core.models import SheetEntry, AddressListEntry, SuspensionPreview
from core.interfaces import SheetReader, MikroTikClient

SUSPEND_LIST = "suspendido"


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


class SuspensionUseCases:
    """Orchestrates the preview + execute flows."""

    def __init__(self, sheets: SheetReader, mikrotik: MikroTikClient) -> None:
        self._sheets = sheets
        self._mikrotik = mikrotik

    async def _sync_new_entries(
        self,
        sheet_entries: list[SheetEntry],
        mkt_entries: list[AddressListEntry],
    ) -> list[AddressListEntry]:
        """Add IPs that are in the sheet but not yet in the MikroTik list."""
        existing_ips = {e.address for e in mkt_entries}
        for entry in sheet_entries:
            if entry.ip not in existing_ips:
                await self._mikrotik.add_address(entry.ip, SUSPEND_LIST, entry.name)

        # Return the refreshed list after addition
        return await self._mikrotik.get_address_list(SUSPEND_LIST)

    async def preview(
        self,
        csv_path: str,
        mikrotik_ip: str,
        date: str,
    ) -> SuspensionPreview:
        """Preview what would be suspended. Also syncs new entries (matching original behaviour)."""
        sheet_entries = await self._sheets.read_entries(csv_path)
        await self._mikrotik.connect(mikrotik_ip)

        current_list = await self._mikrotik.get_address_list(SUSPEND_LIST)
        updated_list = await self._sync_new_entries(sheet_entries, current_list)

        matched, final = _build_comment_map(sheet_entries, updated_list, date)

        await self._mikrotik.disconnect()
        return SuspensionPreview(current_comments=matched, final_comments=final)

    async def execute(
        self,
        csv_path: str,
        mikrotik_ip: str,
        date: str,
    ) -> None:
        """Execute the suspension: sync, disable entries, and update comments."""
        sheet_entries = await self._sheets.read_entries(csv_path)
        await self._mikrotik.connect(mikrotik_ip)

        current_list = await self._mikrotik.get_address_list(SUSPEND_LIST)
        updated_list = await self._sync_new_entries(sheet_entries, current_list)

        matched, final = _build_comment_map(sheet_entries, updated_list, date)

        for entry in matched:
            await self._mikrotik.disable_entry(entry.id)

        for entry in final:
            await self._mikrotik.set_comment(entry.id, entry.comment)

        await self._mikrotik.disconnect()
