"""Integration tests for ingest API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.features.ingest.schemas.ingest import ScanResult, TrackMetadata


@pytest.mark.unit
async def test_scan_requires_auth(async_client: AsyncClient) -> None:
    response = await async_client.post("/api/v1/ingest/scan", json={"directory": "/music"})
    assert response.status_code == 401


@pytest.mark.unit
async def test_scan_rejects_path_traversal(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await async_client.post(
        "/api/v1/ingest/scan",
        json={"directory": "/etc/passwd"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "must be within" in response.json()["error"].lower()


@pytest.mark.unit
async def test_scan_nonexistent_directory(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """A directory that doesn't exist should return scanned=0, not an error."""
    response = await async_client.post(
        "/api/v1/ingest/scan",
        json={"directory": "/music/nonexistent"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scanned"] == 0
    assert data["stored"] == 0


@pytest.mark.unit
async def test_scan_success(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    scan_result = ScanResult(
        scanned=2,
        stored=2,
        tracks=[
            TrackMetadata(file_path="/music/a.mp3", title="A", artist="X"),
            TrackMetadata(file_path="/music/b.mp3", title="B", artist="Y"),
        ],
    )

    with (
        patch("app.features.ingest.api.ingest.Path.is_relative_to", return_value=True),
        patch("app.features.ingest.api.ingest.Path.is_dir", return_value=True),
        patch(
            "app.features.ingest.services.ingest_service.IngestService.scan_and_store",
            new_callable=AsyncMock,
            return_value=scan_result,
        ),
    ):
        response = await async_client.post(
            "/api/v1/ingest/scan",
            json={"directory": "/music"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["scanned"] == 2
    assert data["stored"] == 2
    assert len(data["tracks"]) == 2
