"""Radio settings service."""

from __future__ import annotations

import asyncpg
import structlog

from app.features.settings.repositories import settings_repository as repo
from app.features.settings.schemas.settings import RadioSettingsResponse, RadioSettingsUpdate

logger = structlog.get_logger(__name__)

_DEFAULTS = RadioSettingsResponse(
    station_name="Tramontane",
    language="fr",
    location="",
)


async def get_settings(user_id: str, pool: asyncpg.Pool) -> RadioSettingsResponse:
    """Get radio settings for a user, creating defaults if needed."""
    row = await repo.get_by_user(user_id, pool)
    if row is None:
        await repo.ensure_defaults(user_id, pool)
        return _DEFAULTS

    return RadioSettingsResponse(
        station_name=row["station_name"],
        language=row["language"],
        location=row["location"],
    )


async def update_settings(
    user_id: str,
    data: RadioSettingsUpdate,
    pool: asyncpg.Pool,
) -> RadioSettingsResponse:
    """Update radio settings for a user (upsert)."""
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return await get_settings(user_id, pool)

    await repo.ensure_defaults(user_id, pool)
    await repo.update(user_id, updates, pool)

    return await get_settings(user_id, pool)
