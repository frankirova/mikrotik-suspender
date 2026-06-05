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
