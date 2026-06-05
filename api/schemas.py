"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel, Field


class SuspensionRequest(BaseModel):
    IP_MIKROTIK: str
    DATE: str
    CSV_PATH: str = Field(..., description="Path to the CSV with clients (ip, nombre columns)")


class AddOptionRequest(BaseModel):
    option: str
