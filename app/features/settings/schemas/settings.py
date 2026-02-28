"""Radio settings schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RadioSettingsResponse(BaseModel):
    """Response model for radio settings."""

    station_name: str
    language: str
    location: str


class RadioSettingsUpdate(BaseModel):
    """Request body for updating radio settings."""

    station_name: str | None = Field(None, max_length=100)
    language: str | None = Field(None, pattern=r"^(en|fr|es)$")
    location: str | None = Field(None, max_length=200)
