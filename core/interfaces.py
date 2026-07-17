"""Ports (abstract interfaces) for driven adapters.

These define what the application needs from the outside world,
without committing to any specific technology or library.
"""

from abc import ABC, abstractmethod

from core.models import AddressListEntry, SheetEntry


class SheetReader(ABC):
    """Port for reading entries from a spreadsheet."""

    @abstractmethod
    async def read_entries(self) -> list[SheetEntry]:
        """Read client IPs and names from the configured CSV source."""
        ...


class MikroTikClient(ABC):
    """Port for interacting with a MikroTik RouterOS device."""

    @abstractmethod
    async def connect(self, router: str) -> None:
        """Open a connection to the MikroTik device."""
        ...

    @abstractmethod
    async def get_address_list(self, list_name: str) -> list[AddressListEntry]:
        """Fetch all entries in a firewall address-list."""
        ...

    @abstractmethod
    async def add_address(self, address: str, list_name: str, comment: str) -> None:
        """Add an IP to a firewall address-list."""
        ...

    @abstractmethod
    async def enable_entry(self, entry_id: str) -> None:
        """Set an address-list entry as active (disabled=false in RouterOS).

        In MikroTik semantics: disabled=false means the entry IS applied,
        so the firewall rule that references this address-list will match it.
        """
        ...

    @abstractmethod
    async def set_comment(self, entry_id: str, comment: str) -> None:
        """Update the comment on an address-list entry."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection."""
        ...


class OptionsRepository(ABC):
    """Port for persisting user-defined option IPs."""

    @abstractmethod
    async def add(self, option: str) -> None:
        """Store a single option value."""
        ...

    @abstractmethod
    async def add_many(self, options: list[str]) -> None:
        """Store multiple option values."""
        ...

    @abstractmethod
    async def get_all(self) -> list[str]:
        """Retrieve all stored option values."""
        ...
