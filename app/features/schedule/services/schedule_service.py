"""Schedule block business logic -- CRUD orchestration with overlap validation."""

from __future__ import annotations

import asyncpg
import structlog

from app.core.exceptions import NotFoundError, ValidationError
from app.features.hosts.repositories.host_repository import HostRepository
from app.features.schedule.repositories.schedule_repository import ScheduleRepository
from app.features.schedule.schemas.schedule import (
    ActiveBlockResponse,
    ScheduleBlockCreate,
    ScheduleBlockResponse,
    ScheduleBlockUpdate,
)

logger = structlog.get_logger(__name__)


def _resolve_avatar_url(host_id: str, avatar_url: str | None) -> str | None:
    """Convert a storage path to a proxy URL, pass HTTP URLs through."""
    if not avatar_url:
        return None
    if avatar_url.startswith("http"):
        return avatar_url
    return f"/api/v1/hosts/{host_id}/avatar"


def row_to_response(row: dict) -> ScheduleBlockResponse:
    """Convert a database row (with host join) to a ScheduleBlockResponse."""
    host_id = str(row["host_id"])
    return ScheduleBlockResponse(
        id=str(row["id"]),
        host_id=host_id,
        host_name=row.get("host_name"),
        host_avatar_url=_resolve_avatar_url(host_id, row.get("host_avatar_url")),
        host_template_id=row.get("host_template_id"),
        name=row["name"],
        description=row["description"],
        start_time=str(row["start_time"])[:5],  # HH:MM:SS -> HH:MM
        end_time=str(row["end_time"])[:5],
        day_of_week=row.get("day_of_week"),
        is_active=row["is_active"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


async def create_block(
    data: ScheduleBlockCreate,
    user_id: str,
    pool: asyncpg.Pool,
) -> ScheduleBlockResponse:
    """Create a new schedule block with host validation and overlap check."""
    host_repo = HostRepository(pool)
    schedule_repo = ScheduleRepository(pool)

    # Validate host exists and belongs to user
    host = await host_repo.get_by_id(data.host_id, user_id)
    if host is None:
        raise ValidationError("Host not found or does not belong to you")

    # Check for time overlap
    has_overlap = await schedule_repo.check_overlap(
        data.start_time,
        data.end_time,
        data.day_of_week,
        user_id=user_id,
    )
    if has_overlap:
        raise ValidationError("Schedule block overlaps with an existing block")

    # Create the block
    block_id = await schedule_repo.create(
        user_id=user_id,
        host_id=data.host_id,
        name=data.name,
        description=data.description,
        start_time=data.start_time,
        end_time=data.end_time,
        day_of_week=data.day_of_week,
        is_active=data.is_active,
    )

    # Fetch the created block with host info
    row = await schedule_repo.get_by_id(block_id, user_id)
    if row is None:
        raise NotFoundError("Schedule block")

    logger.info("schedule_block_created", block_id=block_id, name=data.name)
    return row_to_response(row)


async def update_block(
    block_id: str,
    data: ScheduleBlockUpdate,
    user_id: str,
    pool: asyncpg.Pool,
) -> ScheduleBlockResponse | None:
    """Update a schedule block with optional re-validation."""
    schedule_repo = ScheduleRepository(pool)

    # Get existing block to check ownership
    existing = await schedule_repo.get_by_id(block_id, user_id)
    if existing is None:
        return None

    # Build update fields (only provided, non-None values)
    update_fields: dict[str, object] = {}
    _updatable = (
        "host_id", "name", "description", "start_time",
        "end_time", "day_of_week", "is_active",
    )
    for field_name in _updatable:
        value = getattr(data, field_name, None)
        if value is not None:
            update_fields[field_name] = value

    # Handle day_of_week explicitly (can be set to None to mean "every day")
    if data.day_of_week is not None:
        update_fields["day_of_week"] = data.day_of_week

    if not update_fields:
        return row_to_response(existing)

    # If host_id changed, validate new host
    if "host_id" in update_fields:
        host_repo = HostRepository(pool)
        host = await host_repo.get_by_id(str(update_fields["host_id"]), user_id)
        if host is None:
            raise ValidationError("Host not found or does not belong to you")

    # If time changed, re-check overlap (excluding self)
    time_changed = (
        "start_time" in update_fields
        or "end_time" in update_fields
        or "day_of_week" in update_fields
    )
    if time_changed:
        check_start = str(update_fields.get("start_time", existing["start_time"]))[:5]
        check_end = str(update_fields.get("end_time", existing["end_time"]))[:5]
        check_day = update_fields.get("day_of_week", existing.get("day_of_week"))

        has_overlap = await schedule_repo.check_overlap(
            check_start,
            check_end,
            check_day,  # type: ignore[arg-type]
            exclude_id=block_id,
            user_id=user_id,
        )
        if has_overlap:
            raise ValidationError("Schedule block overlaps with an existing block")

    # Perform update
    row = await schedule_repo.update(block_id, user_id, **update_fields)
    if row is None:
        return None

    logger.info("schedule_block_updated", block_id=block_id)
    return row_to_response(row)


async def get_block(
    block_id: str,
    user_id: str,
    pool: asyncpg.Pool,
) -> ScheduleBlockResponse | None:
    """Get a single schedule block by ID."""
    repo = ScheduleRepository(pool)
    row = await repo.get_by_id(block_id, user_id)
    return row_to_response(row) if row else None


async def delete_block(
    block_id: str,
    user_id: str,
    pool: asyncpg.Pool,
) -> bool:
    """Delete a schedule block."""
    repo = ScheduleRepository(pool)
    deleted = await repo.delete(block_id, user_id)
    if deleted:
        logger.info("schedule_block_deleted", block_id=block_id)
    return deleted


async def list_blocks(
    user_id: str,
    pool: asyncpg.Pool,
) -> list[ScheduleBlockResponse]:
    """List all schedule blocks for a user."""
    repo = ScheduleRepository(pool)
    rows = await repo.list_by_user(user_id)
    return [row_to_response(r) for r in rows]


async def get_active_block(
    pool: asyncpg.Pool,
) -> ActiveBlockResponse:
    """Get the currently active schedule block (for now-playing card)."""
    repo = ScheduleRepository(pool)
    row = await repo.get_active_block()

    if row is None:
        return ActiveBlockResponse(block=None, host_name=None, host_avatar_url=None)

    block = row_to_response(row)
    return ActiveBlockResponse(
        block=block,
        host_name=row.get("host_name"),
        host_avatar_url=_resolve_avatar_url(
            str(row["host_id"]), row.get("host_avatar_url"),
        ),
    )
