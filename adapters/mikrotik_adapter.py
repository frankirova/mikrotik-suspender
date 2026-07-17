"""RouterOS adapter with allowlisted targets, TLS and bounded sync calls."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import routeros_api

from core.config import config
from core.interfaces import MikroTikClient
from core.models import AddressListEntry

logger = logging.getLogger(__name__)
T = TypeVar("T")


class RouterOSError(RuntimeError):
    """A classified RouterOS transport or protocol failure."""


class RouterOSSessionUncertainError(RouterOSError):
    """The last operation may still be running in a worker thread."""


class RouterOSClient(MikroTikClient):
    def __init__(self) -> None:
        self._connection: routeros_api.RouterOsApiPool | None = None
        self._api: routeros_api.RouterOsApi | None = None
        self._session_uncertain = False

    async def _call(self, operation: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        if self._session_uncertain:
            raise RouterOSSessionUncertainError(
                "RouterOS session state is uncertain after a timeout; create a new client and "
                "reconcile with a fresh plan"
            )
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(operation, *args, **kwargs),
                timeout=config.router_timeout,
            )
        except TimeoutError as exc:
            self._session_uncertain = True
            raise RouterOSSessionUncertainError(
                "RouterOS operation timed out and may still be running; session state is uncertain"
            ) from exc
        except (OSError, routeros_api.exceptions.RouterOsApiError) as exc:
            raise RouterOSError(f"RouterOS operation failed: {type(exc).__name__}") from exc

    async def connect(self, router: str) -> None:
        try:
            target = config.routers[router]
        except KeyError as exc:
            raise ValueError(f"unknown router alias: {router}") from exc
        if not config.router_tls or not config.router_tls_verify:
            logger.critical("insecure RouterOS transport enabled by explicit configuration")
        connection = await self._call(
            routeros_api.RouterOsApiPool,
            target.host,
            username=config.mikrotik_user,
            password=config.mikrotik_password,
            port=target.port,
            plaintext_login=True,
            use_ssl=config.router_tls,
            ssl_verify=config.router_tls_verify,
            ssl_verify_hostname=config.router_tls_verify,
        )
        self._connection = connection
        self._api = await self._call(connection.get_api)

    def _resource(self):
        if self._api is None:
            raise RuntimeError("not connected to RouterOS")
        return self._api.get_resource("/ip/firewall/address-list")

    async def get_address_list(self, list_name: str) -> list[AddressListEntry]:
        raw = await self._call(self._resource().get, list=list_name)
        return [
            AddressListEntry(
                id=entry["id"],
                address=entry["address"],
                comment=entry.get("comment", ""),
                disabled=str(entry.get("disabled", "false")).lower() in {"true", "yes"},
            )
            for entry in raw
        ]

    async def add_address(self, address: str, list_name: str, comment: str) -> None:
        await self._call(self._resource().add, address=address, list=list_name, comment=comment)

    async def enable_entry(self, entry_id: str) -> None:
        await self._call(self._resource().set, id=entry_id, disabled="false")

    async def set_comment(self, entry_id: str, comment: str) -> None:
        await self._call(self._resource().set, id=entry_id, comment=comment)

    async def disconnect(self) -> None:
        if self._session_uncertain:
            logger.error(
                "RouterOS disconnect skipped because a timed-out worker may still use "
                "the connection"
            )
            return
        connection, self._connection, self._api = self._connection, None, None
        if connection is not None:
            await self._call(connection.disconnect)
