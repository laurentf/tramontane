"""Integration tests for host API endpoints."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.features.hosts.schemas.hosts import (
    EnrichmentResult,
    HostResponse,
    TemplateSchema,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HOST = HostResponse(
    id="h1",
    name="DJ",
    template_id="chill_dj",
    avatar_url=None,
    avatar_status="pending",
    voice_id=None,
    voice_provider="elevenlabs",
    status="active",
    created_at="2025-01-01",
    updated_at="2025-01-01",
)

_TEMPLATE = TemplateSchema(
    template_id="chill_dj",
    name={"en": "Chill DJ", "fr": "DJ Chill"},
    description={"en": "Relaxed DJ", "fr": "DJ d\u00e9tendu"},
    icon="\U0001f3a7",
    general_fields=[],
    template_fields=[],
    default_voices={"elevenlabs": {"male": "v1", "female": "v2"}},
    avatar_generation_params={},
    avatar_style_hint="cartoon style",
    enrichment_prompt="Create profile for {name}",
)


@pytest.fixture(autouse=True)
def _seed_admin_cache() -> None:
    """Pre-populate the admin cache so require_admin skips the DB lookup."""
    from app.core.security import _admin_cache

    _admin_cache["test-user-id"] = (True, time.monotonic())


# ---------------------------------------------------------------------------
# Templates (public)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_list_templates(async_client: AsyncClient) -> None:
    """GET /api/v1/hosts/templates returns the template list."""
    with patch(
        "app.features.hosts.api.hosts.list_templates",
        return_value=[_TEMPLATE],
    ):
        response = await async_client.get("/api/v1/hosts/templates")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["template_id"] == "chill_dj"
    # Default locale is "fr"
    assert data[0]["name"] == "DJ Chill"


@pytest.mark.unit
async def test_list_templates_with_locale(async_client: AsyncClient) -> None:
    """GET /api/v1/hosts/templates?locale=en returns English names."""
    with patch(
        "app.features.hosts.api.hosts.list_templates",
        return_value=[_TEMPLATE],
    ):
        response = await async_client.get("/api/v1/hosts/templates?locale=en")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Chill DJ"


@pytest.mark.unit
async def test_get_questionnaire_found(async_client: AsyncClient) -> None:
    """GET /api/v1/hosts/templates/{id}/questionnaire returns fields."""
    with patch(
        "app.features.hosts.api.hosts.get_template",
        return_value=_TEMPLATE,
    ):
        response = await async_client.get(
            "/api/v1/hosts/templates/chill_dj/questionnaire"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["template_id"] == "chill_dj"
    assert isinstance(data["fields"], list)


@pytest.mark.unit
async def test_get_questionnaire_not_found(async_client: AsyncClient) -> None:
    """GET /api/v1/hosts/templates/{id}/questionnaire returns 404 for unknown id."""
    with patch(
        "app.features.hosts.api.hosts.get_template",
        return_value=None,
    ):
        response = await async_client.get(
            "/api/v1/hosts/templates/unknown/questionnaire"
        )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Host CRUD (admin-protected)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_create_host_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/hosts returns 201 on success."""
    with patch(
        "app.features.hosts.api.hosts.host_service.create_host",
        new_callable=AsyncMock,
        return_value=_HOST,
    ):
        response = await async_client.post(
            "/api/v1/hosts",
            json={"name": "DJ", "template_id": "chill_dj", "description": {}},
            headers=auth_headers,
        )

    assert response.status_code == 201
    assert response.json()["id"] == "h1"
    assert response.json()["name"] == "DJ"


@pytest.mark.unit
async def test_create_host_requires_auth(async_client: AsyncClient) -> None:
    """POST /api/v1/hosts without auth returns 401."""
    response = await async_client.post(
        "/api/v1/hosts",
        json={"name": "DJ", "template_id": "chill_dj"},
    )
    assert response.status_code == 401


@pytest.mark.unit
async def test_list_hosts(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/hosts returns host list."""
    with patch(
        "app.features.hosts.api.hosts.host_service.list_all_hosts",
        new_callable=AsyncMock,
        return_value=[_HOST],
    ):
        response = await async_client.get("/api/v1/hosts", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "h1"


@pytest.mark.unit
async def test_get_host_found(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/hosts/{id} returns the host when found."""
    with patch(
        "app.features.hosts.api.hosts.host_service.get_host_public",
        new_callable=AsyncMock,
        return_value=_HOST,
    ):
        response = await async_client.get("/api/v1/hosts/h1", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == "h1"


@pytest.mark.unit
async def test_get_host_not_found(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/hosts/{id} returns 404 when not found."""
    with patch(
        "app.features.hosts.api.hosts.host_service.get_host_public",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = await async_client.get("/api/v1/hosts/nope", headers=auth_headers)

    assert response.status_code == 404


@pytest.mark.unit
async def test_update_host_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """PATCH /api/v1/hosts/{id} returns updated host."""
    with patch(
        "app.features.hosts.api.hosts.host_service.update_host",
        new_callable=AsyncMock,
        return_value=_HOST,
    ):
        response = await async_client.patch(
            "/api/v1/hosts/h1",
            json={"name": "DJ Updated"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["id"] == "h1"


@pytest.mark.unit
async def test_delete_host_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """DELETE /api/v1/hosts/{id} returns 204 on success."""
    with patch(
        "app.features.hosts.api.hosts.host_service.delete_host",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = await async_client.delete(
            "/api/v1/hosts/h1", headers=auth_headers
        )

    assert response.status_code == 204


@pytest.mark.unit
async def test_delete_host_not_found(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """DELETE /api/v1/hosts/{id} returns 404 when host does not exist."""
    with patch(
        "app.features.hosts.api.hosts.host_service.delete_host",
        new_callable=AsyncMock,
        return_value=False,
    ):
        response = await async_client.delete(
            "/api/v1/hosts/nope", headers=auth_headers
        )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_enrich_host_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/hosts/{id}/enrich returns enrichment result."""
    enrichment = EnrichmentResult(
        short_summary="A chill DJ",
        self_description="I am a chill DJ who loves lo-fi beats.",
        avatar_prompt="A cartoon DJ with headphones",
    )
    mock_settings = MagicMock()
    mock_settings.language = "fr"

    with (
        patch(
            "app.features.hosts.api.hosts.settings_service.get_settings",
            new_callable=AsyncMock,
            return_value=mock_settings,
        ),
        patch(
            "app.features.hosts.api.hosts.host_service.enrich_host_profile",
            new_callable=AsyncMock,
            return_value=enrichment,
        ),
    ):
        response = await async_client.post(
            "/api/v1/hosts/h1/enrich", headers=auth_headers
        )

    assert response.status_code == 200
    data = response.json()
    assert data["short_summary"] == "A chill DJ"
    assert data["self_description"] == "I am a chill DJ who loves lo-fi beats."
    assert data["avatar_prompt"] == "A cartoon DJ with headphones"


@pytest.mark.unit
async def test_enrich_host_ai_error_returns_503(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/hosts/{id}/enrich returns 503 on AIProviderError."""
    from app.providers.ai_exceptions import AIProviderError

    mock_settings = MagicMock()
    mock_settings.language = "fr"

    with (
        patch(
            "app.features.hosts.api.hosts.settings_service.get_settings",
            new_callable=AsyncMock,
            return_value=mock_settings,
        ),
        patch(
            "app.features.hosts.api.hosts.host_service.enrich_host_profile",
            new_callable=AsyncMock,
            side_effect=AIProviderError("mistral", "LLM unavailable"),
        ),
    ):
        response = await async_client.post(
            "/api/v1/hosts/h1/enrich", headers=auth_headers
        )

    assert response.status_code == 503
