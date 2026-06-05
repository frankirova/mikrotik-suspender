"""API authentication — optional Bearer token validation.

When the `API_KEY` env var is set, all protected endpoints require:

    Authorization: Bearer <API_KEY>

When unset, this dependency is a no-op (dev mode). A WARNING is logged at
application startup so it's obvious that authentication is disabled.

Token comparison uses `secrets.compare_digest()` to prevent timing attacks.
"""
from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status


def _get_api_key() -> str | None:
    """Read the configured key. Indirection so tests can monkeypatch it."""
    from core.config import config
    return config.api_key


async def verify_api_key(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """FastAPI dependency that validates the Bearer token if auth is enabled.

    Raises 401 on missing/malformed header or invalid token. Becomes a no-op
    when `API_KEY` is not configured (development mode).
    """
    api_key = _get_api_key()
    if not api_key:
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Missing or malformed Authorization header. "
                "Expected: 'Authorization: Bearer <api-key>'"
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(provided, api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
