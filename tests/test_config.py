import importlib
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from core.config import RouterConfig, _routers


@pytest.mark.parametrize("address_list", [None, "", "with space", "-starts-with-dash"])
def test_router_address_list_is_required_and_validated(monkeypatch, address_list) -> None:
    item = {"host": "192.0.2.10"}
    if address_list is not None:
        item["address_list"] = address_list
    monkeypatch.setenv("ROUTERS_JSON", __import__("json").dumps({"lab": item}))

    with pytest.raises(RuntimeError, match="Invalid ROUTERS_JSON"):
        _routers()


def test_empty_router_mapping_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("ROUTERS_JSON", "{}")

    with pytest.raises(RuntimeError, match="at least one router is required"):
        RouterConfig("operator", "password")


def test_modules_import_without_router_secrets(monkeypatch) -> None:
    for key in ("USER_MIKROTIK", "PASS_MIKROTIK", "ROUTERS_JSON"):
        monkeypatch.delenv(key, raising=False)
    for module in ("core.config", "main", "cli.__main__", "adapters.mikrotik_adapter"):
        importlib.import_module(module)


def test_cli_help_does_not_require_router_secrets() -> None:
    env = os.environ.copy()
    for key in ("USER_MIKROTIK", "PASS_MIKROTIK", "ROUTERS_JSON", "API_KEY"):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-m", "cli", "--help"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert "usage: mikrotik-suspender" in result.stdout


def test_router_config_fails_closed_at_adapter_boundary(monkeypatch) -> None:
    for key in ("USER_MIKROTIK", "PASS_MIKROTIK", "ROUTERS_JSON"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="USER_MIKROTIK"):
        RouterConfig()


def test_server_startup_fails_without_router_config(monkeypatch) -> None:
    from main import api

    for key in ("USER_MIKROTIK", "PASS_MIKROTIK", "ROUTERS_JSON"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="USER_MIKROTIK"), TestClient(api):
        pass
    response = TestClient(api).get("/health/ready")
    assert response.status_code == 503


def test_server_startup_and_readiness_fail_with_empty_router_mapping(monkeypatch) -> None:
    from main import api

    monkeypatch.setenv("USER_MIKROTIK", "operator")
    monkeypatch.setenv("PASS_MIKROTIK", "password")
    monkeypatch.setenv("ROUTERS_JSON", "{}")
    with pytest.raises(RuntimeError, match="at least one router is required"), TestClient(api):
        pass
    assert TestClient(api).get("/health/ready").status_code == 503


def test_server_is_ready_with_valid_router_config(monkeypatch, tmp_path) -> None:
    import main

    monkeypatch.setenv("USER_MIKROTIK", "operator")
    monkeypatch.setenv("PASS_MIKROTIK", "secret")
    monkeypatch.setenv(
        "ROUTERS_JSON", '{"edge":{"host":"192.0.2.1","address_list":"suspended"}}'
    )
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CSV_PATH", str(tmp_path / "clientes.csv"))
    monkeypatch.setenv("OPTIONS_DB_PATH", str(tmp_path / "options.db"))
    main.config = main.AppConfig()
    with TestClient(main.api) as client:
        assert client.get("/health/ready").json() == {"status": "ready"}
    assert TestClient(main.api).get("/health/ready").status_code == 503


@pytest.mark.parametrize(("tls", "port"), [("true", 8729), ("false", 8728)])
def test_router_port_defaults_from_transport(monkeypatch, tls, port) -> None:
    monkeypatch.setenv("ROUTER_TLS", tls)
    monkeypatch.setenv(
        "ROUTERS_JSON", '{"edge":{"host":"192.0.2.1","address_list":"suspended"}}'
    )
    assert _routers()["edge"].port == port
