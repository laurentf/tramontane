"""Unit tests for schedule business logic -- service + repository."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ValidationError
from app.features.schedule.repositories.schedule_repository import ScheduleRepository
from app.features.schedule.schemas.schedule import (
    ActiveBlockResponse,
    ScheduleBlockCreate,
    ScheduleBlockUpdate,
)
from app.features.schedule.services import schedule_service
from app.features.schedule.services.schedule_service import (
    row_to_response,
)

USER_ID = "test-user-id"
BLOCK_ID = "block-123"
HOST_ID = "host-456"


def _make_row(**overrides: object) -> dict:
    """Build a mock schedule-block row with host join columns."""
    row: dict = {
        "id": BLOCK_ID,
        "host_id": HOST_ID,
        "host_name": "DJ Cool",
        "host_avatar_url": None,
        "host_template_id": "chill_dj",
        "name": "Morning Show",
        "description": "Wake up vibes",
        "start_time": "08:00:00",
        "end_time": "10:00:00",
        "day_of_week": None,
        "is_active": True,
        "user_id": USER_ID,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class TestScheduleRepositoryCreate:
    @pytest.mark.unit
    async def test_create_returns_id(self, mock_db_pool: AsyncMock) -> None:
        mock_conn = mock_db_pool.acquire().__aenter__.return_value
        mock_conn.fetchval = AsyncMock(return_value="new-block-id")

        repo = ScheduleRepository(mock_db_pool)
        result = await repo.create(
            user_id=USER_ID,
            host_id=HOST_ID,
            name="Morning Show",
            description="Wake up vibes",
            start_time="08:00",
            end_time="10:00",
            day_of_week=None,
            is_active=True,
        )

        assert result == "new-block-id"
        mock_conn.fetchval.assert_called_once()


class TestScheduleRepositoryGetById:
    @pytest.mark.unit
    async def test_get_by_id_found(self, mock_db_pool: AsyncMock) -> None:
        row = _make_row()
        mock_conn = mock_db_pool.acquire().__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=MagicMock(**row))
        # asyncpg Record is dict-like, but we mock dict() conversion
        mock_conn.fetchrow.return_value = row

        repo = ScheduleRepository(mock_db_pool)
        result = await repo.get_by_id(BLOCK_ID, USER_ID)

        assert result is not None
        assert result["id"] == BLOCK_ID
        assert result["host_name"] == "DJ Cool"

    @pytest.mark.unit
    async def test_get_by_id_not_found(self, mock_db_pool: AsyncMock) -> None:
        mock_conn = mock_db_pool.acquire().__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=None)

        repo = ScheduleRepository(mock_db_pool)
        result = await repo.get_by_id("nonexistent", USER_ID)

        assert result is None


class TestScheduleRepositoryListByUser:
    @pytest.mark.unit
    async def test_list_by_user(self, mock_db_pool: AsyncMock) -> None:
        rows = [_make_row(id="b1"), _make_row(id="b2")]
        mock_conn = mock_db_pool.acquire().__aenter__.return_value
        mock_conn.fetch = AsyncMock(return_value=rows)

        repo = ScheduleRepository(mock_db_pool)
        result = await repo.list_by_user(USER_ID)

        assert len(result) == 2
        assert result[0]["id"] == "b1"
        assert result[1]["id"] == "b2"


class TestScheduleRepositoryUpdate:
    @pytest.mark.unit
    async def test_update_valid_column(self, mock_db_pool: AsyncMock) -> None:
        updated_row = _make_row(name="Afternoon Show")
        mock_conn = mock_db_pool.acquire().__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=updated_row)

        repo = ScheduleRepository(mock_db_pool)
        result = await repo.update(BLOCK_ID, USER_ID, name="Afternoon Show")

        assert result is not None
        assert result["name"] == "Afternoon Show"

    @pytest.mark.unit
    async def test_update_invalid_column_raises(self, mock_db_pool: AsyncMock) -> None:
        repo = ScheduleRepository(mock_db_pool)

        with pytest.raises(ValueError, match="Invalid column"):
            await repo.update(BLOCK_ID, USER_ID, hacker_field="drop table")


class TestScheduleRepositoryDelete:
    @pytest.mark.unit
    async def test_delete_success(self, mock_db_pool: AsyncMock) -> None:
        mock_conn = mock_db_pool.acquire().__aenter__.return_value
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        repo = ScheduleRepository(mock_db_pool)
        result = await repo.delete(BLOCK_ID, USER_ID)

        assert result is True

    @pytest.mark.unit
    async def test_delete_not_found(self, mock_db_pool: AsyncMock) -> None:
        mock_conn = mock_db_pool.acquire().__aenter__.return_value
        mock_conn.execute = AsyncMock(return_value="DELETE 0")

        repo = ScheduleRepository(mock_db_pool)
        result = await repo.delete("nonexistent", USER_ID)

        assert result is False


class TestScheduleRepositoryCheckOverlap:
    @pytest.mark.unit
    async def test_check_overlap_true(self, mock_db_pool: AsyncMock) -> None:
        mock_conn = mock_db_pool.acquire().__aenter__.return_value
        mock_conn.fetchval = AsyncMock(return_value=True)

        repo = ScheduleRepository(mock_db_pool)
        result = await repo.check_overlap(
            "08:00", "10:00", None, user_id=USER_ID,
        )

        assert result is True

    @pytest.mark.unit
    async def test_check_overlap_false(self, mock_db_pool: AsyncMock) -> None:
        mock_conn = mock_db_pool.acquire().__aenter__.return_value
        mock_conn.fetchval = AsyncMock(return_value=False)

        repo = ScheduleRepository(mock_db_pool)
        result = await repo.check_overlap(
            "12:00", "14:00", None, user_id=USER_ID,
        )

        assert result is False


class TestScheduleRepositoryGetActiveBlock:
    @pytest.mark.unit
    async def test_get_active_block_found(self, mock_db_pool: AsyncMock) -> None:
        row = _make_row()
        mock_conn = mock_db_pool.acquire().__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=row)

        repo = ScheduleRepository(mock_db_pool)
        result = await repo.get_active_block()

        assert result is not None
        assert result["id"] == BLOCK_ID

    @pytest.mark.unit
    async def test_get_active_block_none(self, mock_db_pool: AsyncMock) -> None:
        mock_conn = mock_db_pool.acquire().__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=None)

        repo = ScheduleRepository(mock_db_pool)
        result = await repo.get_active_block()

        assert result is None


# ---------------------------------------------------------------------------
# row_to_response / _resolve_avatar_url tests
# ---------------------------------------------------------------------------


class TestRowToResponse:
    @pytest.mark.unit
    def test_avatar_storage_path_becomes_proxy_url(self) -> None:
        row = _make_row(host_avatar_url="avatars/host-456/avatar.png")
        resp = row_to_response(row)

        assert resp.host_avatar_url == f"/api/v1/hosts/{HOST_ID}/avatar"

    @pytest.mark.unit
    def test_avatar_http_url_passed_through(self) -> None:
        row = _make_row(host_avatar_url="https://cdn.example.com/avatar.png")
        resp = row_to_response(row)

        assert resp.host_avatar_url == "https://cdn.example.com/avatar.png"

    @pytest.mark.unit
    def test_avatar_none_stays_none(self) -> None:
        row = _make_row(host_avatar_url=None)
        resp = row_to_response(row)

        assert resp.host_avatar_url is None

    @pytest.mark.unit
    def test_time_truncated_to_hhmm(self) -> None:
        row = _make_row(start_time="08:00:00", end_time="10:30:00")
        resp = row_to_response(row)

        assert resp.start_time == "08:00"
        assert resp.end_time == "10:30"


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestCreateBlock:
    @pytest.mark.unit
    async def test_create_block_success(self, mock_db_pool: AsyncMock) -> None:
        data = ScheduleBlockCreate(
            host_id=HOST_ID,
            name="Morning Show",
            description="Wake up vibes",
            start_time="08:00",
            end_time="10:00",
        )
        row = _make_row()

        with (
            patch(
                "app.features.schedule.services.schedule_service.HostRepository",
            ) as MockHostRepo,
            patch(
                "app.features.schedule.services.schedule_service.ScheduleRepository",
            ) as MockSchedRepo,
        ):
            MockHostRepo.return_value.get_by_id = AsyncMock(return_value={"id": HOST_ID})
            MockSchedRepo.return_value.check_overlap = AsyncMock(return_value=False)
            MockSchedRepo.return_value.create = AsyncMock(return_value=BLOCK_ID)
            MockSchedRepo.return_value.get_by_id = AsyncMock(return_value=row)

            result = await schedule_service.create_block(data, USER_ID, mock_db_pool)

        assert result.id == BLOCK_ID
        assert result.name == "Morning Show"

    @pytest.mark.unit
    async def test_create_block_host_not_found(self, mock_db_pool: AsyncMock) -> None:
        data = ScheduleBlockCreate(
            host_id="nonexistent-host",
            name="Show",
            description="Desc",
            start_time="08:00",
            end_time="10:00",
        )

        with (
            patch(
                "app.features.schedule.services.schedule_service.HostRepository",
            ) as MockHostRepo,
            patch(
                "app.features.schedule.services.schedule_service.ScheduleRepository",
            ),
        ):
            MockHostRepo.return_value.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(ValidationError, match="Host not found"):
                await schedule_service.create_block(data, USER_ID, mock_db_pool)

    @pytest.mark.unit
    async def test_create_block_overlap(self, mock_db_pool: AsyncMock) -> None:
        data = ScheduleBlockCreate(
            host_id=HOST_ID,
            name="Clash Show",
            description="Overlapping",
            start_time="09:00",
            end_time="11:00",
        )

        with (
            patch(
                "app.features.schedule.services.schedule_service.HostRepository",
            ) as MockHostRepo,
            patch(
                "app.features.schedule.services.schedule_service.ScheduleRepository",
            ) as MockSchedRepo,
        ):
            MockHostRepo.return_value.get_by_id = AsyncMock(return_value={"id": HOST_ID})
            MockSchedRepo.return_value.check_overlap = AsyncMock(return_value=True)

            with pytest.raises(ValidationError, match="overlaps"):
                await schedule_service.create_block(data, USER_ID, mock_db_pool)


class TestGetBlock:
    @pytest.mark.unit
    async def test_get_block_found(self, mock_db_pool: AsyncMock) -> None:
        row = _make_row()

        with patch(
            "app.features.schedule.services.schedule_service.ScheduleRepository",
        ) as MockSchedRepo:
            MockSchedRepo.return_value.get_by_id = AsyncMock(return_value=row)

            result = await schedule_service.get_block(BLOCK_ID, USER_ID, mock_db_pool)

        assert result is not None
        assert result.id == BLOCK_ID

    @pytest.mark.unit
    async def test_get_block_not_found(self, mock_db_pool: AsyncMock) -> None:
        with patch(
            "app.features.schedule.services.schedule_service.ScheduleRepository",
        ) as MockSchedRepo:
            MockSchedRepo.return_value.get_by_id = AsyncMock(return_value=None)

            result = await schedule_service.get_block("nope", USER_ID, mock_db_pool)

        assert result is None


class TestListBlocks:
    @pytest.mark.unit
    async def test_list_blocks(self, mock_db_pool: AsyncMock) -> None:
        rows = [_make_row(id="b1", name="Show A"), _make_row(id="b2", name="Show B")]

        with patch(
            "app.features.schedule.services.schedule_service.ScheduleRepository",
        ) as MockSchedRepo:
            MockSchedRepo.return_value.list_by_user = AsyncMock(return_value=rows)

            result = await schedule_service.list_blocks(USER_ID, mock_db_pool)

        assert len(result) == 2
        assert result[0].name == "Show A"
        assert result[1].name == "Show B"


class TestUpdateBlock:
    @pytest.mark.unit
    async def test_update_block_success(self, mock_db_pool: AsyncMock) -> None:
        existing_row = _make_row()
        updated_row = _make_row(name="Updated Show")
        data = ScheduleBlockUpdate(name="Updated Show")

        with patch(
            "app.features.schedule.services.schedule_service.ScheduleRepository",
        ) as MockSchedRepo:
            repo_instance = MockSchedRepo.return_value
            repo_instance.get_by_id = AsyncMock(return_value=existing_row)
            repo_instance.update = AsyncMock(return_value=updated_row)

            result = await schedule_service.update_block(
                BLOCK_ID, data, USER_ID, mock_db_pool,
            )

        assert result is not None
        assert result.name == "Updated Show"


class TestDeleteBlock:
    @pytest.mark.unit
    async def test_delete_block_success(self, mock_db_pool: AsyncMock) -> None:
        with patch(
            "app.features.schedule.services.schedule_service.ScheduleRepository",
        ) as MockSchedRepo:
            MockSchedRepo.return_value.delete = AsyncMock(return_value=True)

            result = await schedule_service.delete_block(BLOCK_ID, USER_ID, mock_db_pool)

        assert result is True


class TestGetActiveBlock:
    @pytest.mark.unit
    async def test_get_active_block_returns_null_block(
        self, mock_db_pool: AsyncMock,
    ) -> None:
        with patch(
            "app.features.schedule.services.schedule_service.ScheduleRepository",
        ) as MockSchedRepo:
            MockSchedRepo.return_value.get_active_block = AsyncMock(return_value=None)

            result = await schedule_service.get_active_block(mock_db_pool)

        assert isinstance(result, ActiveBlockResponse)
        assert result.block is None
        assert result.host_name is None
        assert result.host_avatar_url is None

    @pytest.mark.unit
    async def test_get_active_block_returns_block(
        self, mock_db_pool: AsyncMock,
    ) -> None:
        row = _make_row()

        with patch(
            "app.features.schedule.services.schedule_service.ScheduleRepository",
        ) as MockSchedRepo:
            MockSchedRepo.return_value.get_active_block = AsyncMock(return_value=row)

            result = await schedule_service.get_active_block(mock_db_pool)

        assert isinstance(result, ActiveBlockResponse)
        assert result.block is not None
        assert result.block.id == BLOCK_ID
        assert result.host_name == "DJ Cool"
