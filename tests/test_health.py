"""Smoke tests for health endpoint and auth routes."""

import pytest
from httpx import AsyncClient


@pytest.mark.unit
async def test_health_returns_healthy(async_client: AsyncClient) -> None:
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.unit
async def test_auth_session_requires_auth(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/auth/session")
    assert response.status_code == 401


@pytest.mark.unit
async def test_auth_session_with_token(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await async_client.get("/api/v1/auth/session", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test-user-id"


@pytest.mark.unit
async def test_auth_login(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user_id"] == "test-user-id"


@pytest.mark.unit
async def test_auth_signup(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "new@example.com",
            "password": "strongpassword123",
            "display_name": "New User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == "test-user-id"
