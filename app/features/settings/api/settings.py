"""Radio settings API endpoints."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends

from app.core.deps.db import get_db_pool
from app.core.security import require_admin
from app.features.settings.schemas.settings import RadioSettingsResponse, RadioSettingsUpdate
from app.features.settings.services import settings_service as service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=RadioSettingsResponse)
async def get_settings(
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> RadioSettingsResponse:
    """Get radio settings for the authenticated user."""
    return await service.get_settings(user_id, pool)


@router.patch("", response_model=RadioSettingsResponse)
async def update_settings(
    body: RadioSettingsUpdate,
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> RadioSettingsResponse:
    """Update radio settings for the authenticated user."""
    return await service.update_settings(user_id, body, pool)
