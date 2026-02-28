"""Schedule block CRUD API endpoints."""

from __future__ import annotations

import asyncpg
import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.deps.db import get_db_pool
from app.core.exceptions import NotFoundError
from app.core.security import require_admin
from app.features.schedule.schemas.schedule import (
    ActiveBlockResponse,
    ScheduleBlockCreate,
    ScheduleBlockResponse,
    ScheduleBlockUpdate,
)
from app.features.schedule.services import schedule_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/schedule", tags=["schedule"])


# ---------------------------------------------------------------------------
# Public endpoint (no auth)
# ---------------------------------------------------------------------------


@router.get("/active", response_model=ActiveBlockResponse)
async def get_active_block(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> ActiveBlockResponse:
    """Get the currently active schedule block (for now-playing card).

    No authentication required -- used by the public radio player.
    """
    return await schedule_service.get_active_block(pool)


# ---------------------------------------------------------------------------
# Schedule block CRUD (authenticated)
# ---------------------------------------------------------------------------


@router.post("/blocks", response_model=ScheduleBlockResponse, status_code=201)
async def create_block(
    body: ScheduleBlockCreate,
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> ScheduleBlockResponse:
    """Create a new schedule block."""
    return await schedule_service.create_block(body, user_id, pool)


@router.get("/blocks", response_model=list[ScheduleBlockResponse])
async def list_blocks(
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[ScheduleBlockResponse]:
    """List all schedule blocks for the authenticated user."""
    return await schedule_service.list_blocks(user_id, pool)


@router.get("/blocks/{block_id}", response_model=ScheduleBlockResponse)
async def get_block(
    block_id: str,
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> ScheduleBlockResponse:
    """Get a single schedule block by ID."""
    block = await schedule_service.get_block(block_id, user_id, pool)
    if block is None:
        raise NotFoundError("Schedule block")
    return block


@router.patch("/blocks/{block_id}", response_model=ScheduleBlockResponse)
async def update_block(
    block_id: str,
    body: ScheduleBlockUpdate,
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> ScheduleBlockResponse:
    """Update a schedule block."""
    result = await schedule_service.update_block(block_id, body, user_id, pool)
    if result is None:
        raise NotFoundError("Schedule block")
    return result


@router.delete("/blocks/{block_id}", status_code=204)
async def delete_block(
    block_id: str,
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """Delete a schedule block."""
    deleted = await schedule_service.delete_block(block_id, user_id, pool)
    if not deleted:
        raise NotFoundError("Schedule block")
    return Response(status_code=204)
