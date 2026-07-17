"""Validated application configuration loaded from environment variables."""

from __future__ import annotations

import ipaddress
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ADDRESS_LIST_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _required(key: str) -> str:
    value = _optional(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _bool(key: str, default: bool) -> bool:
    value = _optional(key, str(default)).lower()
    if value not in {"true", "false"}:
        raise RuntimeError(f"{key} must be true or false")
    return value == "true"


@dataclass(frozen=True)
class RouterTarget:
    host: str
    address_list: str
    port: int | None = None


def _routers(tls: bool | None = None) -> dict[str, RouterTarget]:
    raw = _required("ROUTERS_JSON")
    tls = _bool("ROUTER_TLS", True) if tls is None else tls
    try:
        values = json.loads(raw)
        if not isinstance(values, dict) or not values:
            raise ValueError("at least one router is required")
        targets = {
            alias: RouterTarget(
                host=str(item["host"]),
                address_list=str(item["address_list"]),
                port=item.get("port", 8729 if tls else 8728),
            )
            for alias, item in values.items()
        }
        for alias, target in targets.items():
            if not alias or not alias.replace("-", "").replace("_", "").isalnum():
                raise ValueError(f"invalid router alias {alias!r}")
            ipaddress.ip_address(target.host)
            if not ADDRESS_LIST_NAME.fullmatch(target.address_list):
                raise ValueError(f"invalid address-list for router {alias}")
            if target.port is not None and not 1 <= target.port <= 65535:
                raise ValueError(f"invalid port for router {alias}")
        return targets
    except (TypeError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid ROUTERS_JSON: {exc}") from exc


@dataclass(frozen=True)
class AppConfig:
    router_tls: bool = field(default_factory=lambda: _bool("ROUTER_TLS", True))
    router_tls_verify: bool = field(default_factory=lambda: _bool("ROUTER_TLS_VERIFY", True))
    router_timeout: float = field(default_factory=lambda: float(_optional("ROUTER_TIMEOUT", "10")))
    data_dir: Path = field(default_factory=lambda: Path(_optional("DATA_DIR", "./data")).resolve())
    csv_path: Path = field(
        default_factory=lambda: Path(_optional("CSV_PATH", "./data/clientes.csv")).resolve()
    )
    options_db_path: Path = field(
        default_factory=lambda: Path(_optional("OPTIONS_DB_PATH", "./data/options.db")).resolve()
    )
    cors_origins: list[str] = field(
        default_factory=lambda: [_optional("CORS_ORIGIN_1", "http://localhost:8000")]
    )
    host: str = field(default_factory=lambda: _optional("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_optional("PORT", "8000")))
    api_key: str | None = field(default_factory=lambda: _optional("API_KEY") or None)
    max_entries: int = field(default_factory=lambda: int(_optional("MAX_ENTRIES", "1000")))

    def validate_security(self) -> None:
        if self.host not in {"127.0.0.1", "::1", "localhost"} and not self.api_key:
            raise RuntimeError("API_KEY is required when HOST is not loopback")
        if not self.router_tls or not self.router_tls_verify:
            import warnings

            warnings.warn(
                "INSECURE RouterOS transport explicitly enabled",
                RuntimeWarning,
                stacklevel=2,
            )


@dataclass(frozen=True)
class RouterConfig:
    user: str = field(default_factory=lambda: _required("USER_MIKROTIK"))
    password: str = field(default_factory=lambda: _required("PASS_MIKROTIK"))
    routers: dict[str, RouterTarget] = field(default_factory=_routers)
    tls: bool = field(default_factory=lambda: _bool("ROUTER_TLS", True))
    tls_verify: bool = field(default_factory=lambda: _bool("ROUTER_TLS_VERIFY", True))
    timeout: float = field(default_factory=lambda: float(_optional("ROUTER_TIMEOUT", "10")))
