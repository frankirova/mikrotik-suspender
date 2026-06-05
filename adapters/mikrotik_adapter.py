"""MikroTik RouterOS adapter — wraps the routeros-api library."""

from __future__ import annotations

import routeros_api

from core.models import AddressListEntry
from core.interfaces import MikroTikClient
from core.config import config


class RouterOSClient(MikroTikClient):
    """Adapter for MikroTik RouterOS API communication."""

    def __init__(self) -> None:
        self._connection: routeros_api.RouterOsApiPool | None = None
        self._api: routeros_api.RouterOsApi | None = None

    async def connect(self, ip: str) -> None:
        self._connection = routeros_api.RouterOsApiPool(
            ip,
            username=config.mikrotik_user,
            password=config.mikrotik_password,
            plaintext_login=True,
        )
        self._api = self._connection.get_api()

    def _assert_connected(self) -> routeros_api.RouterOsApi:
        if self._api is None:
            raise RuntimeError("Not connected to MikroTik. Call connect() first.")
        return self._api

    async def get_address_list(self, list_name: str) -> list[AddressListEntry]:
        api = self._assert_connected()
        resource = api.get_resource("/ip/firewall/address-list")
        raw = resource.get(list=list_name)
        return [
            AddressListEntry(id=entry["id"], address=entry["address"], comment=entry.get("comment", ""))
            for entry in raw
        ]

    async def add_address(self, address: str, list_name: str, comment: str) -> None:
        api = self._assert_connected()
        resource = api.get_resource("/ip/firewall/address-list")
        resource.add(address=address, list=list_name, comment=comment)

    async def disable_entry(self, entry_id: str) -> None:
        """Activate suspension by setting disabled=false (entry IS applied)."""
        api = self._assert_connected()
        resource = api.get_resource("/ip/firewall/address-list")
        resource.set(id=entry_id, disabled="false")

    async def set_comment(self, entry_id: str, comment: str) -> None:
        api = self._assert_connected()
        resource = api.get_resource("/ip/firewall/address-list")
        resource.set(id=entry_id, comment=comment)

    async def disconnect(self) -> None:
        if self._connection is not None:
            self._connection.disconnect()
        self._connection = None
        self._api = None
