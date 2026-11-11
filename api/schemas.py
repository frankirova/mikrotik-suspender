"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel


class SuspensionRequest(BaseModel):
    IP_MIKROTIK: str
    USER: str
    PASSWORD: str
    DATE: str
    # Optional per-run override of the firewall address-list name.
    # Empty/absent falls back to LIST_NAME (.env), then to "suspendido".
    LIST_NAME: str | None = None


class AddOptionRequest(BaseModel):
    option: str
