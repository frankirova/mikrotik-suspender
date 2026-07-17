import pytest

from core.config import _routers


@pytest.mark.parametrize("address_list", [None, "", "with space", "-starts-with-dash"])
def test_router_address_list_is_required_and_validated(monkeypatch, address_list) -> None:
    item = {"host": "192.0.2.10"}
    if address_list is not None:
        item["address_list"] = address_list
    monkeypatch.setenv("ROUTERS_JSON", __import__("json").dumps({"lab": item}))

    with pytest.raises(RuntimeError, match="Invalid ROUTERS_JSON"):
        _routers()
