from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from core.config import RouterTarget
from core.interfaces import MikroTikClient, SheetReader
from core.models import ActionKind, AddressListEntry, SheetEntry
from use_cases.suspension import PlanRejectedError, SuspensionUseCases


@dataclass
class FakeSheet(SheetReader):
    entries: list[SheetEntry]

    async def read_entries(self) -> list[SheetEntry]:
        return self.entries


class FakeRouter(MikroTikClient):
    def __init__(self, entries: list[AddressListEntry] | None = None) -> None:
        self.entries = list(entries or [])
        self.calls: list[tuple] = []
        self.closed = False
        self.fail_address: str | None = None

    async def connect(self, router: str) -> None:
        self.calls.append(("connect", router))

    async def get_address_list(self, list_name: str) -> list[AddressListEntry]:
        self.calls.append(("get", list_name))
        return list(self.entries)

    async def add_address(self, address: str, list_name: str, comment: str) -> None:
        self.calls.append(("add", address, list_name))
        if address == self.fail_address:
            raise RuntimeError("injected failure")
        self.entries.append(AddressListEntry(f"id-{address}", address, comment))

    async def enable_entry(self, entry_id: str) -> None:
        self.calls.append(("enable", entry_id))
        self.entries = [replace(e, disabled=False) if e.id == entry_id else e for e in self.entries]

    async def set_comment(self, entry_id: str, comment: str) -> None:
        self.calls.append(("comment", entry_id))
        self.entries = [
            replace(e, comment=comment) if e.id == entry_id else e for e in self.entries
        ]

    async def disconnect(self) -> None:
        self.closed = True
        self.calls.append(("disconnect",))


def uc(entries: list[SheetEntry], router: FakeRouter) -> SuspensionUseCases:
    return SuspensionUseCases(
        FakeSheet(entries),
        router,
        {"lab": RouterTarget("192.0.2.10", "lab-suspensions", 8729)},
    )


@pytest.mark.asyncio
async def test_plan_is_strictly_read_only_and_closes_connection() -> None:
    router = FakeRouter()
    plan = await uc([SheetEntry("10.0.0.1", "A", 2)], router).plan("lab", "2026-07-17")
    assert [action.kind for action in plan.actions] == [ActionKind.CREATE]
    assert plan.address_list == "lab-suspensions"
    assert ("get", "lab-suspensions") in router.calls
    assert not any(call[0] in {"add", "enable", "comment"} for call in router.calls)
    assert router.closed


@pytest.mark.asyncio
async def test_managed_comment_is_idempotent() -> None:
    router = FakeRouter([AddressListEntry("*1", "10.0.0.1", "A // SUSPENDIDO - 2025-01-01")])
    use_case = uc([SheetEntry("10.0.0.1", "A", 2)], router)
    first = await use_case.plan("lab", "2026-07-17")
    assert first.actions[0].comment == "A // SUSPENDIDO - 2026-07-17"
    assert (await use_case.apply(first, "lab")).failed == 0
    second = await use_case.plan("lab", "2026-07-17")
    assert [action.kind for action in second.actions] == [ActionKind.NOOP]
    assert ("add", "10.0.0.1", "lab-suspensions") not in router.calls


@pytest.mark.asyncio
async def test_duplicate_input_rejected_with_line() -> None:
    with pytest.raises(ValueError, match="line 3.*line 2"):
        await uc(
            [SheetEntry("10.0.0.1", "A", 2), SheetEntry("10.0.0.1", "B", 3)], FakeRouter()
        ).plan("lab", "2026-07-17")


@pytest.mark.asyncio
async def test_empty_and_invalid_date_rejected_before_connect() -> None:
    router = FakeRouter()
    with pytest.raises(ValueError, match="no entries"):
        await uc([], router).plan("lab", "2026-07-17")
    with pytest.raises(ValueError):
        await uc([SheetEntry("10.0.0.1", "A", 2)], router).plan("lab", "bad")
    assert not router.calls


@pytest.mark.asyncio
async def test_disconnects_when_read_fails() -> None:
    class Broken(FakeRouter):
        async def get_address_list(self, list_name: str):
            raise RuntimeError("boom")

    router = Broken()
    with pytest.raises(RuntimeError, match="boom"):
        await uc([SheetEntry("10.0.0.1", "A", 2)], router).plan("lab", "2026-07-17")
    assert router.closed


@pytest.mark.asyncio
async def test_partial_failure_returns_per_entry_results_and_retry_is_safe() -> None:
    router = FakeRouter()
    router.fail_address = "10.0.0.2"
    use_case = uc([SheetEntry("10.0.0.1", "A", 2), SheetEntry("10.0.0.2", "B", 3)], router)
    plan = await use_case.plan("lab", "2026-07-17")
    result = await use_case.apply(plan, "lab")
    assert (result.succeeded, result.failed) == (1, 1)
    retry = await use_case.plan("lab", "2026-07-17")
    assert {a.kind for a in retry.actions} == {ActionKind.NOOP, ActionKind.CREATE}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["tampered", "stale", "router"])
async def test_rejects_invalid_plan(case: str) -> None:
    router = FakeRouter()
    use_case = uc([SheetEntry("10.0.0.1", "A", 2)], router)
    plan = await use_case.plan("lab", "2026-07-17")
    target = "lab"
    if case == "tampered":
        plan = replace(plan, date="2026-07-18")
    elif case == "stale":
        router.entries.append(AddressListEntry("*x", "10.0.0.9", "X"))
    else:
        target = "other"
    with pytest.raises(PlanRejectedError):
        await use_case.apply(plan, target)


@pytest.mark.asyncio
async def test_apply_uses_bound_address_list_for_writes_and_verification() -> None:
    router = FakeRouter()
    use_case = uc([SheetEntry("10.0.0.1", "A", 2)], router)
    plan = await use_case.plan("lab", "2026-07-17")
    router.calls.clear()

    await use_case.apply(plan, "lab")

    assert ("get", "lab-suspensions") in router.calls
    assert ("add", "10.0.0.1", "lab-suspensions") in router.calls


@pytest.mark.asyncio
async def test_rejects_address_list_mismatch_and_tampering_before_connect() -> None:
    router = FakeRouter()
    use_case = uc([SheetEntry("10.0.0.1", "A", 2)], router)
    plan = await use_case.plan("lab", "2026-07-17")
    router.calls.clear()

    changed_config = SuspensionUseCases(
        FakeSheet([]),
        router,
        {"lab": RouterTarget("192.0.2.10", "other-lab-list", 8729)},
    )
    with pytest.raises(PlanRejectedError, match="another address-list"):
        await changed_config.apply(plan, "lab")
    assert not router.calls

    tampered_config = SuspensionUseCases(
        FakeSheet([]),
        router,
        {"lab": RouterTarget("192.0.2.10", "tampered-list", 8729)},
    )
    tampered = replace(plan, address_list="tampered-list")
    with pytest.raises(PlanRejectedError, match="modified"):
        await tampered_config.apply(tampered, "lab")
    assert not router.calls


@pytest.mark.asyncio
async def test_missing_target_configuration_fails_closed_before_connect() -> None:
    router = FakeRouter()
    use_case = SuspensionUseCases(FakeSheet([SheetEntry("10.0.0.1", "A", 2)]), router, {})

    with pytest.raises(ValueError, match="unknown router alias"):
        await use_case.plan("lab", "2026-07-17")
    assert not router.calls
