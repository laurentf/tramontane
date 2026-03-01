"""Unit tests for host business logic -- repository and service layers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.features.hosts.repositories.host_repository import HostRepository
from app.features.hosts.schemas.hosts import (
    EnrichmentResult,
    HostCreate,
    HostResponse,
    HostUpdate,
)
from app.features.hosts.services import host_service

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

USER_ID = "user-abc"
HOST_ID = "host-123"


def _make_host_row(**overrides: object) -> dict:
    """Build a realistic host row dict with sane defaults."""
    row: dict = {
        "id": HOST_ID,
        "name": "DJ Cool",
        "template_id": "chill_dj",
        "description": {
            "gender": "male",
            "short_summary": "A cool DJ",
            "self_description": "I am cool",
        },
        "avatar_url": None,
        "avatar_status": "pending",
        "avatar_prompt": None,
        "voice_id": "voice-123",
        "voice_provider": "elevenlabs",
        "status": "active",
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    }
    row.update(overrides)
    return row


def _mock_template() -> MagicMock:
    """Return a mock TemplateSchema with default_voices."""
    tpl = MagicMock()
    tpl.default_voices = {"elevenlabs": {"male": "voice-m", "female": "voice-f"}}
    tpl.enrichment_prompt = "Generate profile for {name}. {form_data}. Style: {avatar_style_hint}"
    tpl.avatar_style_hint = "retro cartoon"
    tpl.general_fields = []
    tpl.template_fields = []
    tpl.avatar_generation_params = {}
    return tpl


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class TestHostRepositoryCreate:
    @pytest.mark.unit
    async def test_create_returns_id(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchval = AsyncMock(return_value="new-host-id")

        repo = HostRepository(mock_db_pool)
        result = await repo.create(
            user_id=USER_ID,
            name="DJ Cool",
            template_id="chill_dj",
            description={"gender": "male"},
            voice_id="voice-123",
        )

        assert result == "new-host-id"
        conn.fetchval.assert_called_once()


class TestHostRepositoryGetById:
    @pytest.mark.unit
    async def test_get_by_id_found(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_host_row())

        repo = HostRepository(mock_db_pool)
        result = await repo.get_by_id(HOST_ID, USER_ID)

        assert result is not None
        assert result["id"] == HOST_ID
        assert result["name"] == "DJ Cool"

    @pytest.mark.unit
    async def test_get_by_id_not_found(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=None)

        repo = HostRepository(mock_db_pool)
        result = await repo.get_by_id("nonexistent", USER_ID)

        assert result is None


class TestHostRepositoryListByUser:
    @pytest.mark.unit
    async def test_list_by_user(self, mock_db_pool: AsyncMock) -> None:
        rows = [_make_host_row(id="h1"), _make_host_row(id="h2")]
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetch = AsyncMock(return_value=rows)

        repo = HostRepository(mock_db_pool)
        result = await repo.list_by_user(USER_ID)

        assert len(result) == 2
        assert result[0]["id"] == "h1"
        assert result[1]["id"] == "h2"


class TestHostRepositoryUpdate:
    @pytest.mark.unit
    async def test_update_valid_column(self, mock_db_pool: AsyncMock) -> None:
        updated_row = _make_host_row(name="DJ Updated")
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=updated_row)

        repo = HostRepository(mock_db_pool)
        result = await repo.update(HOST_ID, USER_ID, name="DJ Updated")

        assert result is not None
        assert result["name"] == "DJ Updated"

    @pytest.mark.unit
    async def test_update_invalid_column_raises(self, mock_db_pool: AsyncMock) -> None:
        repo = HostRepository(mock_db_pool)

        with pytest.raises(ValueError, match="Invalid column: hacked"):
            await repo.update(HOST_ID, USER_ID, hacked="drop table")

    @pytest.mark.unit
    async def test_update_no_fields_returns_current(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_host_row())

        repo = HostRepository(mock_db_pool)
        result = await repo.update(HOST_ID, USER_ID)

        assert result is not None
        assert result["id"] == HOST_ID


class TestHostRepositoryDelete:
    @pytest.mark.unit
    async def test_delete_success(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.execute = AsyncMock(return_value="DELETE 1")

        repo = HostRepository(mock_db_pool)
        result = await repo.delete(HOST_ID, USER_ID)

        assert result is True

    @pytest.mark.unit
    async def test_delete_not_found(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.execute = AsyncMock(return_value="DELETE 0")

        repo = HostRepository(mock_db_pool)
        result = await repo.delete(HOST_ID, USER_ID)

        assert result is False


class TestHostRepositoryUpdateAvatar:
    @pytest.mark.unit
    async def test_update_avatar(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.execute = AsyncMock(return_value="UPDATE 1")

        repo = HostRepository(mock_db_pool)
        await repo.update_avatar(
            HOST_ID,
            avatar_url="https://cdn.example.com/avatar.png",
            avatar_status="complete",
            avatar_generation_id="gen-456",
        )

        conn.execute.assert_called_once()
        args = conn.execute.call_args
        assert "https://cdn.example.com/avatar.png" in args[0]
        assert "complete" in args[0]


class TestHostRepositoryDeleteScheduleBlocks:
    @pytest.mark.unit
    async def test_delete_schedule_blocks(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.execute = AsyncMock(return_value="DELETE 3")

        repo = HostRepository(mock_db_pool)
        await repo.delete_schedule_blocks(HOST_ID)

        conn.execute.assert_called_once()
        args = conn.execute.call_args
        assert HOST_ID in args[0]


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestCreateHost:
    @pytest.mark.unit
    async def test_create_host_success(
        self, mock_db_pool: AsyncMock, mock_settings: object
    ) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchval = AsyncMock(return_value=HOST_ID)
        conn.fetchrow = AsyncMock(return_value=_make_host_row())

        data = HostCreate(
            name="DJ Cool",
            template_id="chill_dj",
            description={"gender": "male"},
        )

        with patch(
            "app.features.hosts.services.host_service.get_template",
            return_value=_mock_template(),
        ):
            result = await host_service.create_host(data, USER_ID, mock_db_pool, mock_settings)

        assert isinstance(result, HostResponse)
        assert result.id == HOST_ID
        assert result.name == "DJ Cool"

    @pytest.mark.unit
    async def test_create_host_bad_template(
        self, mock_db_pool: AsyncMock, mock_settings: object
    ) -> None:
        data = HostCreate(
            name="Bad Host",
            template_id="nonexistent_template",
            description={},
        )

        with (
            patch(
                "app.features.hosts.services.host_service.get_template",
                return_value=None,
            ),
            pytest.raises(ValidationError, match="Unknown template"),
        ):
            await host_service.create_host(data, USER_ID, mock_db_pool, mock_settings)


class TestGetHost:
    @pytest.mark.unit
    async def test_get_host_found(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_host_row())

        result = await host_service.get_host(HOST_ID, USER_ID, mock_db_pool)

        assert result is not None
        assert isinstance(result, HostResponse)
        assert result.id == HOST_ID
        assert result.short_summary == "A cool DJ"

    @pytest.mark.unit
    async def test_get_host_not_found(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=None)

        result = await host_service.get_host("nonexistent", USER_ID, mock_db_pool)

        assert result is None


class TestListHosts:
    @pytest.mark.unit
    async def test_list_hosts(self, mock_db_pool: AsyncMock) -> None:
        rows = [_make_host_row(id="h1", name="Host A"), _make_host_row(id="h2", name="Host B")]
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetch = AsyncMock(return_value=rows)

        result = await host_service.list_hosts(USER_ID, mock_db_pool)

        assert len(result) == 2
        assert all(isinstance(r, HostResponse) for r in result)
        assert result[0].id == "h1"
        assert result[1].id == "h2"


class TestUpdateHost:
    @pytest.mark.unit
    async def test_update_host(self, mock_db_pool: AsyncMock) -> None:
        updated_row = _make_host_row(name="DJ Updated")
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=updated_row)

        data = HostUpdate(name="DJ Updated")
        result = await host_service.update_host(HOST_ID, data, USER_ID, mock_db_pool)

        assert result is not None
        assert result.name == "DJ Updated"

    @pytest.mark.unit
    async def test_update_host_no_fields(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=_make_host_row())

        data = HostUpdate()
        result = await host_service.update_host(HOST_ID, data, USER_ID, mock_db_pool)

        assert result is not None
        assert result.id == HOST_ID


class TestDeleteHost:
    @pytest.mark.unit
    async def test_delete_host_cascades_schedule_blocks(
        self, mock_db_pool: AsyncMock
    ) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.execute = AsyncMock(side_effect=["DELETE 2", "DELETE 1"])

        result = await host_service.delete_host(HOST_ID, USER_ID, mock_db_pool)

        assert result is True
        # Two execute calls: delete_schedule_blocks then delete host
        assert conn.execute.call_count == 2

    @pytest.mark.unit
    async def test_delete_host_not_found(self, mock_db_pool: AsyncMock) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.execute = AsyncMock(side_effect=["DELETE 0", "DELETE 0"])

        result = await host_service.delete_host(HOST_ID, USER_ID, mock_db_pool)

        assert result is False


class TestEnrichHostProfile:
    @pytest.mark.unit
    async def test_enrich_host_profile_success(
        self, mock_db_pool: AsyncMock, mock_settings: object
    ) -> None:
        row = _make_host_row()
        enrichment = EnrichmentResult(
            short_summary="sum", self_description="desc", avatar_prompt="prompt"
        )

        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=row)

        with (
            patch(
                "app.features.hosts.services.host_service.get_template",
                return_value=_mock_template(),
            ),
            patch(
                "app.features.hosts.services.host_service.enrich_host",
                new_callable=AsyncMock,
                return_value=enrichment,
            ),
        ):
            result = await host_service.enrich_host_profile(
                HOST_ID, USER_ID, mock_db_pool, mock_settings
            )

        assert isinstance(result, EnrichmentResult)
        assert result.short_summary == "sum"
        assert result.self_description == "desc"
        assert result.avatar_prompt == "prompt"

    @pytest.mark.unit
    async def test_enrich_host_not_found(
        self, mock_db_pool: AsyncMock, mock_settings: object
    ) -> None:
        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await host_service.enrich_host_profile(
                "nonexistent", USER_ID, mock_db_pool, mock_settings
            )

    @pytest.mark.unit
    async def test_enrich_host_enqueues_avatar_when_redis_available(
        self, mock_db_pool: AsyncMock, mock_settings: object
    ) -> None:
        row = _make_host_row()
        enrichment = EnrichmentResult(
            short_summary="sum", self_description="desc", avatar_prompt="prompt"
        )

        conn = mock_db_pool.acquire().__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=row)
        conn.execute = AsyncMock(return_value="UPDATE 1")

        mock_redis = AsyncMock()

        with (
            patch(
                "app.features.hosts.services.host_service.get_template",
                return_value=_mock_template(),
            ),
            patch(
                "app.features.hosts.services.host_service.enrich_host",
                new_callable=AsyncMock,
                return_value=enrichment,
            ),
            patch(
                "app.features.hosts.services.host_service.avatar_service.enqueue_avatar_generation",
                new_callable=AsyncMock,
            ) as mock_enqueue,
        ):
            await host_service.enrich_host_profile(
                HOST_ID, USER_ID, mock_db_pool, mock_settings, redis_pool=mock_redis
            )

        mock_enqueue.assert_called_once_with(mock_redis, HOST_ID)


class TestRowToResponse:
    @pytest.mark.unit
    async def test_row_to_response_with_dict_description(self) -> None:
        row = _make_host_row()
        result = host_service._row_to_response(row)

        assert isinstance(result, HostResponse)
        assert result.id == HOST_ID
        assert result.short_summary == "A cool DJ"
        assert result.self_description == "I am cool"

    @pytest.mark.unit
    async def test_row_to_response_with_string_description(self) -> None:
        row = _make_host_row(
            description='{"short_summary": "JSON string", "self_description": "from str"}'
        )
        result = host_service._row_to_response(row)

        assert result.short_summary == "JSON string"
        assert result.self_description == "from str"

    @pytest.mark.unit
    async def test_row_to_response_with_null_description(self) -> None:
        row = _make_host_row(description=None)
        result = host_service._row_to_response(row)

        assert result.short_summary is None
        assert result.self_description is None
