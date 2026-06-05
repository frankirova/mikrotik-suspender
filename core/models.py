"""Domain models — represent pure business concepts with no infrastructure concerns."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SheetEntry:
    """A client entry from the Google Sheet."""
    ip: str
    name: str


@dataclass(frozen=True)
class AddressListEntry:
    """An entry in the MikroTik firewall address-list."""
    id: str
    address: str
    comment: str


@dataclass(frozen=True)
class SuspensionPreview:
    """Result of a preview run: before and after comment states."""
    current_comments: list[AddressListEntry]
    final_comments: list[AddressListEntry]
