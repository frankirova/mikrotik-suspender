"""Read-only planning and verified application of suspension plans."""

from __future__ import annotations

import re
from datetime import date as date_type

from core.config import RouterTarget
from core.interfaces import MikroTikClient, SheetReader
from core.models import (
    ActionKind,
    ApplyResult,
    EntryResult,
    PlanAction,
    SheetEntry,
    SuspensionPlan,
    address_list_hash,
)

MANAGED_SUFFIX = re.compile(r"\s*// SUSPENDIDO - \d{4}-\d{2}-\d{2}\s*$")


class PlanRejectedError(RuntimeError):
    pass


def _managed_comment(name: str, day: str) -> str:
    return f"{MANAGED_SUFFIX.sub('', name).strip()} // SUSPENDIDO - {day}"


class SuspensionUseCases:
    def __init__(
        self,
        sheets: SheetReader,
        mikrotik: MikroTikClient,
        targets: dict[str, RouterTarget],
        max_entries: int = 1000,
    ) -> None:
        self._sheets = sheets
        self._mikrotik = mikrotik
        self._targets = targets
        self._max_entries = max_entries

    async def plan(self, router: str, date: str) -> SuspensionPlan:
        date_type.fromisoformat(date)
        address_list = self._target_list(router)
        sheet_entries = await self._sheets.read_entries()
        self._validate_entries(sheet_entries)
        await self._mikrotik.connect(router)
        try:
            current = await self._mikrotik.get_address_list(address_list)
        finally:
            await self._mikrotik.disconnect()

        by_address: dict[str, list] = {}
        for entry in current:
            by_address.setdefault(entry.address, []).append(entry)

        actions: list[PlanAction] = []
        for source in sheet_entries:
            matches = by_address.get(source.ip, [])
            final_comment = _managed_comment(source.name, date)
            if len(matches) > 1:
                actions.append(
                    PlanAction(
                        ActionKind.CONFLICT,
                        source.ip,
                        None,
                        final_comment,
                        "duplicate RouterOS entries",
                    )
                )
            elif not matches:
                actions.append(
                    PlanAction(
                        ActionKind.CREATE, source.ip, None, final_comment, "address is missing"
                    )
                )
            else:
                existing = matches[0]
                if existing.disabled:
                    actions.append(
                        PlanAction(
                            ActionKind.ENABLE,
                            source.ip,
                            existing.id,
                            final_comment,
                            "entry is disabled",
                        )
                    )
                if existing.comment != final_comment:
                    actions.append(
                        PlanAction(
                            ActionKind.UPDATE_COMMENT,
                            source.ip,
                            existing.id,
                            final_comment,
                            "managed comment differs",
                        )
                    )
                if not existing.disabled and existing.comment == final_comment:
                    actions.append(
                        PlanAction(
                            ActionKind.NOOP,
                            source.ip,
                            existing.id,
                            final_comment,
                            "already reconciled",
                        )
                    )
        return SuspensionPlan.create(
            router, address_list, date, address_list_hash(current), tuple(actions)
        )

    async def apply(self, plan: SuspensionPlan, router: str) -> ApplyResult:
        if plan.router != router:
            raise PlanRejectedError("plan belongs to another router")
        address_list = self._target_list(router)
        if plan.address_list != address_list:
            raise PlanRejectedError("plan belongs to another address-list")
        expected = SuspensionPlan.create(
            plan.router, plan.address_list, plan.date, plan.snapshot_hash, plan.actions
        )
        if expected.plan_id != plan.plan_id:
            raise PlanRejectedError("plan content or ID was modified")
        if any(action.kind is ActionKind.CONFLICT for action in plan.actions):
            raise PlanRejectedError("plan contains unresolved conflicts")

        await self._mikrotik.connect(router)
        results: list[EntryResult] = []
        try:
            current = await self._mikrotik.get_address_list(address_list)
            if address_list_hash(current) != plan.snapshot_hash:
                raise PlanRejectedError("plan is stale; create a new plan")
            for action in plan.actions:
                try:
                    await self._apply_action(action, address_list)
                    await self._verify_action(action, address_list)
                    results.append(EntryResult(action.address, action.kind, True, "verified"))
                except Exception as exc:
                    results.append(EntryResult(action.address, action.kind, False, str(exc)))
        finally:
            await self._mikrotik.disconnect()
        return ApplyResult(plan.plan_id, tuple(results))

    async def _apply_action(self, action: PlanAction, address_list: str) -> None:
        if action.kind is ActionKind.CREATE:
            await self._mikrotik.add_address(action.address, address_list, action.comment)
        elif action.kind is ActionKind.ENABLE:
            await self._mikrotik.enable_entry(action.entry_id or "")
        elif action.kind is ActionKind.UPDATE_COMMENT:
            await self._mikrotik.set_comment(action.entry_id or "", action.comment)

    async def _verify_action(self, action: PlanAction, address_list: str) -> None:
        if action.kind is ActionKind.NOOP:
            return
        entries = await self._mikrotik.get_address_list(address_list)
        matches = [entry for entry in entries if entry.address == action.address]
        if len(matches) != 1:
            raise RuntimeError("post-write verification found zero or duplicate entries")
        entry = matches[0]
        if (
            action.kind in {ActionKind.CREATE, ActionKind.UPDATE_COMMENT}
            and entry.comment != action.comment
        ):
            raise RuntimeError("post-write comment verification failed")
        if action.kind is ActionKind.ENABLE and entry.disabled:
            raise RuntimeError("post-write enabled verification failed")

    def _target_list(self, router: str) -> str:
        try:
            return self._targets[router].address_list
        except KeyError as exc:
            raise ValueError(f"unknown router alias: {router}") from exc

    def _validate_entries(self, entries: list[SheetEntry]) -> None:
        if not entries:
            raise ValueError("CSV contains no entries")
        if len(entries) > self._max_entries:
            raise ValueError(f"CSV exceeds MAX_ENTRIES ({self._max_entries})")
        seen: dict[str, int] = {}
        for entry in entries:
            if entry.ip in seen:
                raise ValueError(
                    f"line {entry.line}: duplicate IP; first seen at line {seen[entry.ip]}"
                )
            seen[entry.ip] = entry.line
