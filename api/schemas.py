"""Pydantic transport schemas."""

from datetime import date

from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    router: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    date: date


class ApplyRequest(BaseModel):
    router: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    plan_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmed: bool


class AddOptionRequest(BaseModel):
    option: str
