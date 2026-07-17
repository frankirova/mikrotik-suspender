"""Tests for API authentication (optional Bearer token via API_KEY env var)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import api


@pytest.fixture
def client_no_auth(monkeypatch):
    """TestClient with auth DISABLED (no API_KEY configured)."""
    monkeypatch.setattr("api.auth._get_api_key", lambda: None)
    return TestClient(api)


@pytest.fixture
def client_with_auth(monkeypatch):
    """TestClient with auth ENABLED (API_KEY = 'test-key-123')."""
    monkeypatch.setattr("api.auth._get_api_key", lambda: "test-key-123")
    return TestClient(api)


# ── Auth disabled (dev mode) ──────────────────────────────────


def test_health_accessible_without_auth(client_no_auth):
    """Health check works regardless of auth state."""
    r = client_no_auth.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_protected_endpoint_works_without_header_when_disabled(client_no_auth):
    """When API_KEY is unset, protected endpoints accept requests with no header."""
    r = client_no_auth.get("/readOptions")
    assert r.status_code == 200


# ── Auth enabled ──────────────────────────────────────────────


def test_health_still_public_when_auth_enabled(client_with_auth):
    """Health check must remain accessible — it's for external probes."""
    r = client_with_auth.get("/health")
    assert r.status_code == 200


def test_rejects_missing_header(client_with_auth):
    """No Authorization header → 401."""
    r = client_with_auth.get("/readOptions")
    assert r.status_code == 401
    assert "Missing or malformed Authorization header" in r.json()["detail"]
    assert r.headers.get("WWW-Authenticate") == "Bearer"


def test_rejects_non_bearer_scheme(client_with_auth):
    """Authorization with non-Bearer scheme → 401."""
    r = client_with_auth.get(
        "/readOptions",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert r.status_code == 401


def test_rejects_invalid_key(client_with_auth):
    """Bearer with wrong key → 401."""
    r = client_with_auth.get(
        "/readOptions",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid API key"


def test_accepts_valid_key(client_with_auth):
    """Bearer with correct key → handler runs (200)."""
    r = client_with_auth.get(
        "/readOptions",
        headers={"Authorization": "Bearer test-key-123"},
    )
    assert r.status_code == 200
    assert "data" in r.json()


def test_bearer_token_is_trimmed(client_with_auth):
    """Leading/trailing whitespace in the token is tolerated."""
    r = client_with_auth.get(
        "/readOptions",
        headers={"Authorization": "Bearer  test-key-123  "},
    )
    assert r.status_code == 200


def test_non_loopback_configuration_fails_closed():
    from dataclasses import replace

    from core.config import config

    with pytest.raises(RuntimeError, match="API_KEY is required"):
        replace(config, host="0.0.0.0", api_key=None).validate_security()


def test_frontend_keeps_token_in_memory_only():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "static/js/app.js").read_text()
    assert "Authorization" in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source


def test_container_bind_uses_validated_config_and_requires_api_key():
    from pathlib import Path

    root = Path(__file__).parents[1]
    dockerfile = (root / "Dockerfile").read_text()
    compose = (root / "docker-compose.yml").read_text()
    server = (root / "mikrotik_suspender/server.py").read_text()
    assert "HOST=0.0.0.0" in dockerfile
    assert "mikrotik_suspender.server" in dockerfile
    assert "host=config.host" in server
    assert "config.validate_security()" in server
    assert "API_KEY: ${API_KEY:?" in compose


def test_frontend_reports_partial_apply_counts():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "static/js/app.js").read_text()
    assert "summary.changed" in source
    assert "summary.noop" in source
    assert "summary.failed" in source
    assert "failed ? 'error' : 'success'" in source
