"""Thin FastAPI router — delegates everything to use cases.

No business logic lives here. This is pure transport-layer glue.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from api.schemas import SuspensionRequest, AddOptionRequest
from api.dependencies import get_suspension_use_cases, get_options_use_cases
from bootstrap import DEFAULT_OPTIONS

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Suspension endpoints ──────────────────────────────────────

@router.post("/preview")
async def preview(body: SuspensionRequest) -> list[list[dict[str, str]]]:
    """Preview what would happen when suspending the listed IPs.

    Returns the same shape as the original API: [[comment_list], [comment_finally]].
    Each entry has {id, comment} — matching the pre-refactor contract.
    """
    try:
        uc = get_suspension_use_cases()
        result = await uc.preview(
            csv_path=body.CSV_PATH,
            mikrotik_ip=body.IP_MIKROTIK,
            date=body.DATE,
        )
        return [
            [{"id": e.id, "comment": e.comment} for e in result.current_comments],
            [{"id": e.id, "comment": e.comment} for e in result.final_comments],
        ]
    except Exception:
        logger.exception("request failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/script")
async def script(body: SuspensionRequest) -> dict[str, str]:
    """Execute the suspension on the MikroTik device."""
    try:
        uc = get_suspension_use_cases()
        await uc.execute(
            csv_path=body.CSV_PATH,
            mikrotik_ip=body.IP_MIKROTIK,
            date=body.DATE,
        )
        return {"message": "done"}
    except Exception:
        logger.exception("request failed")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Options endpoints ─────────────────────────────────────────


@router.post("/addOptions")
async def add_options() -> dict[str, str]:
    """Insert the default IP options into the SQLite database (idempotent)."""
    try:
        uc = get_options_use_cases()
        await uc.add_defaults(DEFAULT_OPTIONS)
        return {"message": "Datos agregados correctamente"}
    except Exception:
        logger.exception("request failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/readOptions")
async def read_options() -> dict[str, list[str]]:
    """Return all stored option IPs."""
    try:
        uc = get_options_use_cases()
        data = await uc.list_options()
        return {"data": data}
    except Exception:
        logger.exception("request failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/addDoc")
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
