"""Thin FastAPI router — delegates everything to use cases.

No business logic lives here. This is pure transport-layer glue.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.schemas import SuspensionRequest, AddOptionRequest
from api.dependencies import get_suspension_use_cases, get_options_use_cases
from api.auth import verify_api_key
from core.config import config
from bootstrap import DEFAULT_OPTIONS

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Suspension endpoints ──────────────────────────────────────

@router.post("/preview", dependencies=[Depends(verify_api_key)])
async def preview(body: SuspensionRequest) -> list[list[dict[str, str]] | dict[str, object]]:
    """Preview what would happen when suspending the listed IPs.

    Returns [[current_comments], [final_comments], meta]. The first two elements
    keep the original contract; the third adds the effective list name and
    whether any firewall rule matches it.
    """
    try:
        uc = get_suspension_use_cases()
        result = await uc.preview(
            mikrotik_ip=body.IP_MIKROTIK,
            date=body.DATE,
            list_name=body.LIST_NAME,
        )
        return [
            [{"id": e.id, "comment": e.comment} for e in result.current_comments],
            [{"id": e.id, "comment": e.comment} for e in result.final_comments],
            {
                "list_name": result.list_name,
                "list_has_entries": result.list_has_entries,
                "referenced_by_rules": result.referenced_by_rules,
            },
        ]
    except Exception:
        logger.exception("request failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/script", dependencies=[Depends(verify_api_key)])
async def script(body: SuspensionRequest) -> dict[str, str]:
    """Execute the suspension on the MikroTik device."""
    try:
        uc = get_suspension_use_cases()
        await uc.execute(
            mikrotik_ip=body.IP_MIKROTIK,
            date=body.DATE,
            list_name=body.LIST_NAME,
        )
        return {"message": "done"}
    except Exception:
        logger.exception("request failed")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Options endpoints ─────────────────────────────────────────


@router.post("/addOptions", dependencies=[Depends(verify_api_key)])
async def add_options() -> dict[str, str]:
    """Insert the default IP options into the SQLite database (idempotent)."""
    try:
        uc = get_options_use_cases()
        await uc.add_defaults(DEFAULT_OPTIONS)
        return {"message": "Datos agregados correctamente"}
    except Exception:
        logger.exception("request failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/readOptions", dependencies=[Depends(verify_api_key)])
async def read_options() -> dict[str, list[str]]:
    """Return all stored option IPs."""
    try:
        uc = get_options_use_cases()
        data = await uc.list_options()
        return {"data": data}
    except Exception:
        logger.exception("request failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/addDoc", dependencies=[Depends(verify_api_key)])
async def add_doc(body: AddOptionRequest) -> dict[str, str]:
    """Add a single option IP."""
    try:
        uc = get_options_use_cases()
        await uc.add_option(body.option)
        return {"message": "Documento agregado correctamente"}
    except Exception:
        logger.exception("request failed")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Health ────────────────────────────────────────────────────

@router.get("/health")
async def health() -> dict[str, str]:
    """Lightweight health check — used by the bootstrap to confirm wiring."""
    return {"status": "ok"}


# ── Public config ─────────────────────────────────────────────

@router.get("/config")
async def public_config() -> dict[str, str]:
    """Non-secret configuration the UI/CLI need to show effective defaults."""
    return {"list_name": config.list_name}
