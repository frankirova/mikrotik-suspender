import threading
from dataclasses import replace

import pytest

from adapters.mikrotik_adapter import (
    RouterOSClient,
    RouterOSSessionUncertainError,
)
from core.config import RouterConfig, RouterTarget

CONFIG = RouterConfig("user", "password", {"lab": RouterTarget("192.0.2.1", "suspended")})


class Resource:
    def get(self, **kwargs):
        return [{"id": "*1", "address": "10.0.0.1", "comment": "A", "disabled": "yes"}]

    def add(self, **kwargs):
        self.added = kwargs

    def set(self, **kwargs):
        self.updated = kwargs


class API:
    def __init__(self):
        self.resource = Resource()

    def get_resource(self, path):
        assert path == "/ip/firewall/address-list"
        return self.resource


@pytest.mark.asyncio
async def test_contract_maps_representative_routeros_response():
    client = RouterOSClient(CONFIG)
    client._api = API()
    entries = await client.get_address_list("lab-suspensions")
    assert entries[0].disabled is True
    assert entries[0].address == "10.0.0.1"


@pytest.mark.asyncio
async def test_contract_writes_expected_words():
    client = RouterOSClient(CONFIG)
    api = API()
    client._api = api
    await client.add_address("10.0.0.2", "lab-suspensions", "B")
    assert api.resource.added == {
        "address": "10.0.0.2",
        "list": "lab-suspensions",
        "comment": "B",
    }
    await client.enable_entry("*2")
    assert api.resource.updated == {"id": "*2", "disabled": "false"}


@pytest.mark.asyncio
async def test_timeout_quarantines_session_without_concurrent_disconnect(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    disconnected = False

    class Connection:
        def disconnect(self):
            nonlocal disconnected
            disconnected = True

    def blocked_operation():
        started.set()
        release.wait(timeout=1)

    client = RouterOSClient(replace(CONFIG, timeout=0.01))
    client._connection = Connection()
    try:
        with pytest.raises(RouterOSSessionUncertainError, match="may still be running"):
            await client._call(blocked_operation)
        assert started.is_set()
        with pytest.raises(RouterOSSessionUncertainError, match="fresh plan"):
            await client._call(lambda: None)
        await client.disconnect()
        assert disconnected is False
    finally:
        release.set()
