"""Shared pytest fixtures for all tests."""

import os
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from slowapi import Limiter

# Set test environment variables BEFORE importing app code.
# pydantic-settings reads .env which has REDIS_URL pointing to a Docker Redis;
# clearing the settings cache + swapping the limiter avoids any real Redis I/O.
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key-1234567890")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret-key-1234567890")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:54322/test")
os.environ.setdefault("ADMIN_EMAILS", '["admin@test.com"]')
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')

import app.core.rate_limit as _rl
from app.core.config import Settings, get_settings
from app.core.deps import get_db_pool, get_supabase_client

get_settings.cache_clear()
_rl.limiter = Limiter(key_func=_rl.get_user_id_or_ip, storage_uri="memory://")

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def mock_settings() -> Settings:
    """Mock Settings for testing."""
    return Settings(
        _env_file=None,
        supabase_url="https://test.supabase.co",
        supabase_publishable_key="test-publishable-key-1234567890",
        supabase_secret_key="test-secret-key-1234567890",
        database_url="postgresql://test:test@localhost:54322/test",
        admin_emails=["admin@test.com"],
        debug=True,
        cors_origins=["http://localhost:3000"],
    )


def make_mock_verify(user_id: str = "test-user-id"):
    """Create a mock _verify_token that returns a payload for the given user_id."""

    def _mock_verify(token: str, settings: Settings) -> dict:
        return {
            "sub": user_id,
            "aud": "authenticated",
            "exp": 9999999999,
            "iat": 1000000000,
        }

    return _mock_verify


@pytest.fixture
def mock_db_pool() -> AsyncMock:
    """Mock asyncpg connection pool for testing."""
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value="SELECT 1")

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)
    mock_pool.acquire().__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire().__aexit__ = AsyncMock(return_value=None)

    return mock_pool


@pytest.fixture
def mock_supabase_client() -> AsyncMock:
    """Mock Supabase async client for testing."""
    mock_client = AsyncMock()

    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"

    mock_session = MagicMock()
    mock_session.access_token = "test-access-token"
    mock_session.refresh_token = "test-refresh-token"

    mock_auth_response = MagicMock()
    mock_auth_response.user = mock_user
    mock_auth_response.session = mock_session

    mock_oauth_response = MagicMock()
    mock_oauth_response.url = "https://accounts.google.com/oauth"

    mock_client.auth.sign_up = AsyncMock(return_value=mock_auth_response)
    mock_client.auth.sign_in_with_password = AsyncMock(return_value=mock_auth_response)
    mock_client.auth.sign_out = AsyncMock(return_value=None)
    mock_client.auth.get_user = AsyncMock(return_value=mock_user)
    mock_client.auth.sign_in_with_oauth = AsyncMock(return_value=mock_oauth_response)

    return mock_client


@pytest.fixture
async def async_client(
    mock_settings: Settings,
    mock_db_pool: AsyncMock,
    mock_supabase_client: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client with dependency overrides for testing."""
    app.dependency_overrides[get_settings] = lambda: mock_settings

    async def override_get_db_pool():
        return mock_db_pool

    app.dependency_overrides[get_db_pool] = override_get_db_pool
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client

    try:
        with (
            patch("app.core.security._verify_token", side_effect=make_mock_verify()),
            patch("main.create_pool", AsyncMock(return_value=mock_db_pool)),
            patch("main.acreate_client", AsyncMock(return_value=mock_supabase_client)),
        ):
            async with LifespanManager(app):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Authorization headers for authenticated endpoint tests."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def make_auth_headers() -> Any:
    """Factory fixture to generate Authorization headers."""

    def _make_headers(user_id: str = "test-user-id") -> dict[str, str]:
        return {"Authorization": f"Bearer test-token-{user_id}"}

    return _make_headers
