"""Schedule block schemas: Pydantic models for request/response validation."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator

_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _validate_time(v: str, field_name: str) -> str:
    if not _TIME_RE.match(v):
        raise ValueError(f"{field_name} must be in HH:MM format (00:00-23:59)")
    return v


class ScheduleBlockCreate(BaseModel):
    """Request body for creating a schedule block."""

    host_id: str
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=1000)
    start_time: str  # HH:MM format
    end_time: str  # HH:MM format
    day_of_week: int | None = Field(None, ge=0, le=6)
    is_active: bool = True

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, v: str) -> str:
        return _validate_time(v, "start_time")

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: str) -> str:
        return _validate_time(v, "end_time")

    @model_validator(mode="after")
    def check_end_after_start(self) -> ScheduleBlockCreate:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ScheduleBlockUpdate(BaseModel):
    """Request body for updating a schedule block."""

    host_id: str | None = None
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1, max_length=1000)
    start_time: str | None = None  # HH:MM format
    end_time: str | None = None  # HH:MM format
    day_of_week: int | None = None
    is_active: bool | None = None

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_time(v, "start_time")
        return v

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_time(v, "end_time")
        return v


class ScheduleBlockResponse(BaseModel):
    """Response model for a schedule block."""

    id: str
    host_id: str
    host_name: str | None = None  # joined from hosts table
    host_avatar_url: str | None = None  # joined from hosts table
    host_template_id: str | None = None  # for frontend coloring by host type
    name: str
    description: str
    start_time: str
    end_time: str
    day_of_week: int | None = None
    is_active: bool
    created_at: str
    updated_at: str


class ActiveBlockResponse(BaseModel):
    """Response model for the currently active schedule block."""

    block: ScheduleBlockResponse | None = None
    host_name: str | None = None
    host_avatar_url: str | None = None
