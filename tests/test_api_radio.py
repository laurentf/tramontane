"""Integration tests for radio API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.features.radio.schemas.radio import NowPlaying


@pytest.mark.unit
async def test_now_playing_no_auth_required(async_client: AsyncClient) -> None:
    """The now-playing endpoint should be public (no auth required)."""
    with patch(
        "app.features.radio.services.icecast_client.get_now_playing",
        new_callable=AsyncMock,
        return_value=NowPlaying(
            title="Test Song", artist="Test Artist", genre="Rock", listeners=10
        ),
    ):
        response = await async_client.get("/api/v1/radio/now-playing")

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Song"
    assert data["artist"] == "Test Artist"
    assert data["listeners"] == 10


@pytest.mark.unit
async def test_now_playing_returns_defaults_on_error(async_client: AsyncClient) -> None:
    with patch(
        "app.features.radio.services.icecast_client.get_now_playing",
        new_callable=AsyncMock,
        return_value=NowPlaying(),
    ):
        response = await async_client.get("/api/v1/radio/now-playing")

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Unknown Track"
    assert data["artist"] == "Unknown Artist"


@pytest.mark.unit
async def test_push_requires_auth(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/radio/push", json={"file_path": "/music/song.mp3"}
    )
    assert response.status_code == 401


@pytest.mark.unit
async def test_push_rejects_path_outside_music(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await async_client.post(
        "/api/v1/radio/push",
        json={"file_path": "/etc/passwd"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.unit
async def test_push_file_not_found(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    with patch("app.features.radio.api.radio.Path.is_relative_to", return_value=True):
        response = await async_client.post(
            "/api/v1/radio/push",
            json={"file_path": "/music/nonexistent.mp3"},
            headers=auth_headers,
        )

    assert response.status_code == 404


@pytest.mark.unit
async def test_push_success(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    with (
        patch("app.features.radio.api.radio.Path.is_relative_to", return_value=True),
        patch("app.features.radio.api.radio.Path.is_file", return_value=True),
        patch(
            "app.features.radio.services.liquidsoap_client.push_track",
            new_callable=AsyncMock,
            return_value={"status": "ok", "result": "queued"},
        ),
    ):
        response = await async_client.post(
            "/api/v1/radio/push",
            json={"file_path": "/music/song.mp3"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
