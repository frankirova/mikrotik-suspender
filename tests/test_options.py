"""Unit tests for the options management use case."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from core.interfaces import OptionsRepository
from use_cases.options_mgmt import OptionsUseCases


@dataclass
class _FakeOptionsRepo(OptionsRepository):
    store: list[str] = field(default_factory=list)

    async def add(self, option: str) -> None:
        self.store.append(option)

    async def add_many(self, options: list[str]) -> None:
        self.store.extend(options)

    async def get_all(self) -> list[str]:
        return list(self.store)


@pytest.fixture
def repo() -> _FakeOptionsRepo:
    return _FakeOptionsRepo()


@pytest.fixture
def use_cases(repo) -> OptionsUseCases:
    return OptionsUseCases(repo=repo)


@pytest.mark.asyncio
async def test_add_and_list_single_option(use_cases, repo):
    await use_cases.add_option("10.0.0.1")
    assert await use_cases.list_options() == ["10.0.0.1"]


@pytest.mark.asyncio
async def test_add_defaults(use_cases, repo):
    defaults = ["10.0.0.1", "10.0.0.2"]
    await use_cases.add_defaults(defaults)
    assert await use_cases.list_options() == defaults


@pytest.mark.asyncio
async def test_empty_list_when_nothing_stored(use_cases):
    assert await use_cases.list_options() == []
