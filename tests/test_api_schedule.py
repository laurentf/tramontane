"""Integration tests for schedule API endpoints."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.features.schedule.schemas.schedule import (
    ActiveBlockResponse,
    ScheduleBlockResponse,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BLOCK = ScheduleBlockResponse(
    id="b1",
    host_id="h1",
    name="Show",
    description="desc",
    start_time="08:00",
    end_time="10:00",
    is_active=True,
    created_at="2025-01-01",
    updated_at="2025-01-01",
)


@pytest.fixture(autouse=True)
def _seed_admin_cache() -> None:
    """Pre-populate the admin cache so require_admin skips the DB lookup."""
    from app.core.security import _admin_cache

    _admin_cache["test-user-id"] = (True, time.monotonic())


# ---------------------------------------------------------------------------
# Public endpoint
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_get_active_block_no_auth_required(async_client: AsyncClient) -> None:
    """GET /api/v1/schedule/active is public (no auth needed)."""
    with patch(
        "app.features.schedule.api.schedule.schedule_service.get_active_block",
        new_callable=AsyncMock,
        return_value=ActiveBlockResponse(block=None, host_name=None, host_avatar_url=None),
    ):
        response = await async_client.get("/api/v1/schedule/active")

    assert response.status_code == 200
    data = response.json()
    assert data["block"] is None


@pytest.mark.unit
async def test_get_active_block_with_data(async_client: AsyncClient) -> None:
    """GET /api/v1/schedule/active returns block when one is active."""
    active = ActiveBlockResponse(
        block=_BLOCK,
        host_name="DJ Chill",
        host_avatar_url="/api/v1/hosts/h1/avatar",
    )
    with patch(
        "app.features.schedule.api.schedule.schedule_service.get_active_block",
        new_callable=AsyncMock,
        return_value=active,
    ):
        response = await async_client.get("/api/v1/schedule/active")

    assert response.status_code == 200
    data = response.json()
    assert data["block"]["id"] == "b1"
    assert data["host_name"] == "DJ Chill"


# ---------------------------------------------------------------------------
# Schedule block CRUD (admin-protected)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_create_block_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/schedule/blocks returns 201 on success."""
    with patch(
        "app.features.schedule.api.schedule.schedule_service.create_block",
        new_callable=AsyncMock,
        return_value=_BLOCK,
    ):
        response = await async_client.post(
            "/api/v1/schedule/blocks",
            json={
                "host_id": "h1",
                "name": "Show",
                "description": "desc",
                "start_time": "08:00",
                "end_time": "10:00",
            },
            headers=auth_headers,
        )

    assert response.status_code == 201
    assert response.json()["id"] == "b1"


@pytest.mark.unit
async def test_list_blocks(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/schedule/blocks returns block list."""
    with patch(
        "app.features.schedule.api.schedule.schedule_service.list_blocks",
        new_callable=AsyncMock,
        return_value=[_BLOCK],
    ):
        response = await async_client.get(
            "/api/v1/schedule/blocks", headers=auth_headers
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "b1"


@pytest.mark.unit
async def test_get_block_found(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/schedule/blocks/{id} returns the block when found."""
    with patch(
        "app.features.schedule.api.schedule.schedule_service.get_block",
        new_callable=AsyncMock,
        return_value=_BLOCK,
    ):
        response = await async_client.get(
            "/api/v1/schedule/blocks/b1", headers=auth_headers
        )

    assert response.status_code == 200
    assert response.json()["id"] == "b1"


@pytest.mark.unit
async def test_get_block_not_found(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/schedule/blocks/{id} returns 404 when not found."""
    with patch(
        "app.features.schedule.api.schedule.schedule_service.get_block",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = await async_client.get(
            "/api/v1/schedule/blocks/nope", headers=auth_headers
        )

    assert response.status_code == 404


@pytest.mark.unit
async def test_update_block_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """PATCH /api/v1/schedule/blocks/{id} returns updated block."""
    with patch(
        "app.features.schedule.api.schedule.schedule_service.update_block",
        new_callable=AsyncMock,
        return_value=_BLOCK,
    ):
        response = await async_client.patch(
            "/api/v1/schedule/blocks/b1",
            json={"name": "Updated Show"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["id"] == "b1"


@pytest.mark.unit
async def test_update_block_not_found(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """PATCH /api/v1/schedule/blocks/{id} returns 404 when not found."""
    with patch(
        "app.features.schedule.api.schedule.schedule_service.update_block",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = await async_client.patch(
            "/api/v1/schedule/blocks/b1",
            json={"name": "Updated Show"},
            headers=auth_headers,
        )

    assert response.status_code == 404


@pytest.mark.unit
async def test_delete_block_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """DELETE /api/v1/schedule/blocks/{id} returns 204 on success."""
    with patch(
        "app.features.schedule.api.schedule.schedule_service.delete_block",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = await async_client.delete(
            "/api/v1/schedule/blocks/b1", headers=auth_headers
        )

    assert response.status_code == 204


@pytest.mark.unit
async def test_delete_block_not_found(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """DELETE /api/v1/schedule/blocks/{id} returns 404 when not found."""
    with patch(
        "app.features.schedule.api.schedule.schedule_service.delete_block",
        new_callable=AsyncMock,
        return_value=False,
    ):
        response = await async_client.delete(
            "/api/v1/schedule/blocks/nope", headers=auth_headers
        )

    assert response.status_code == 404
