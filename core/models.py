"""Immutable domain models for planning and applying suspensions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256


@dataclass(frozen=True)
class SheetEntry:
    ip: str
    name: str
    line: int = 0


@dataclass(frozen=True)
class AddressListEntry:
    id: str
    address: str
    comment: str
    disabled: bool = False


class ActionKind(StrEnum):
    CREATE = "create"
    ENABLE = "enable"
    UPDATE_COMMENT = "update_comment"
    NOOP = "noop"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class PlanAction:
    kind: ActionKind
    address: str
    entry_id: str | None
    comment: str
    reason: str


@dataclass(frozen=True)
class SuspensionPlan:
    plan_id: str
    router: str
    address_list: str
    date: str
    snapshot_hash: str
    actions: tuple[PlanAction, ...]

    @classmethod
    def create(
        cls,
        router: str,
        address_list: str,
        date: str,
        snapshot_hash: str,
        actions: tuple[PlanAction, ...],
    ) -> SuspensionPlan:
        payload = {
            "router": router,
            "address_list": address_list,
            "date": date,
            "snapshot_hash": snapshot_hash,
            "actions": [asdict(action) for action in actions],
        }
        plan_id = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return cls(plan_id, router, address_list, date, snapshot_hash, actions)


@dataclass(frozen=True)
class EntryResult:
    address: str
    action: ActionKind
    success: bool
    detail: str


@dataclass(frozen=True)
class ApplyResult:
    plan_id: str
    results: tuple[EntryResult, ...]

    @property
    def succeeded(self) -> int:
        return sum(result.success for result in self.results)

    @property
    def failed(self) -> int:
        return len(self.results) - self.succeeded

    @property
    def changed(self) -> int:
        return sum(
            result.success and result.action is not ActionKind.NOOP for result in self.results
        )

    @property
    def noop(self) -> int:
        return sum(result.success and result.action is ActionKind.NOOP for result in self.results)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "changed": self.changed,
            "noop": self.noop,
            "failed": self.failed,
        }


def address_list_hash(entries: list[AddressListEntry]) -> str:
    payload = [asdict(entry) for entry in sorted(entries, key=lambda item: item.id)]
    return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
