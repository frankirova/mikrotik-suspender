"""Use case for managing option IPs stored in MongoDB."""

from __future__ import annotations

from core.interfaces import OptionsRepository


class OptionsUseCases:
    """CRUD-style use cases for option IPs."""

    def __init__(self, repo: OptionsRepository) -> None:
        self._repo = repo

    async def add_option(self, option: str) -> None:
        await self._repo.add(option)

    async def add_defaults(self, options: list[str]) -> None:
        await self._repo.add_many(options)

    async def list_options(self) -> list[str]:
        return await self._repo.get_all()
