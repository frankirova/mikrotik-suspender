"""HTTP endpoints for validate, plan, apply and health status."""

from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from api.auth import verify_api_key
from api.dependencies import get_options_use_cases, get_suspension_use_cases
from api.schemas import AddOptionRequest, ApplyRequest, PlanRequest
from bootstrap import DEFAULT_OPTIONS
from core.models import SuspensionPlan
from use_cases.suspension import PlanRejectedError

logger = logging.getLogger(__name__)
router = APIRouter()
_plans: dict[str, SuspensionPlan] = {}


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError | PlanRejectedError):
        return HTTPException(
            status_code=409 if isinstance(exc, PlanRejectedError) else 422, detail=str(exc)
        )
    logger.exception("request_failed", extra={"error_type": type(exc).__name__})
    return HTTPException(status_code=503, detail="RouterOS operation failed")


@router.post("/validate", dependencies=[Depends(verify_api_key)])
async def validate(body: PlanRequest) -> dict:
    try:
        plan = await get_suspension_use_cases().plan(body.router, body.date.isoformat())
        return {"valid": True, "entries": len({a.address for a in plan.actions})}
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/plan", dependencies=[Depends(verify_api_key)])
async def plan(body: PlanRequest) -> dict:
    try:
        result = await get_suspension_use_cases().plan(body.router, body.date.isoformat())
        _plans[result.plan_id] = result
        return asdict(result)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/apply", dependencies=[Depends(verify_api_key)])
async def apply(body: ApplyRequest) -> dict:
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="explicit confirmation is required")
    stored = _plans.get(body.plan_id)
    if stored is None:
        raise HTTPException(status_code=409, detail="unknown or expired plan; create a new plan")
    try:
        result = await get_suspension_use_cases().apply(stored, body.router)
        _plans.pop(body.plan_id, None)
        payload = asdict(result)
        payload["summary"] = result.summary
        return payload
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/addOptions", dependencies=[Depends(verify_api_key)])
async def add_options() -> dict[str, str]:
    await get_options_use_cases().add_defaults(DEFAULT_OPTIONS)
    return {"message": "Options added"}


@router.get("/readOptions", dependencies=[Depends(verify_api_key)])
async def read_options() -> dict[str, list[str]]:
    return {"data": await get_options_use_cases().list_options()}


@router.post("/addDoc", dependencies=[Depends(verify_api_key)])
async def add_doc(body: AddOptionRequest) -> dict[str, str]:
    await get_options_use_cases().add_option(body.option)
    return {"message": "Option added"}


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> dict[str, str]:
    from core.config import config

    if not config.csv_path.parent.exists():
        raise HTTPException(status_code=503, detail="data directory unavailable")
    return {"status": "ready"}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
