"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel


class SuspensionRequest(BaseModel):
    IP_MIKROTIK: str
    DATE: str


class AddOptionRequest(BaseModel):
    option: str
