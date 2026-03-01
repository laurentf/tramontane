"""Unit tests for settings service and repository."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.features.settings.repositories import settings_repository
from app.features.settings.schemas.settings import RadioSettingsResponse, RadioSettingsUpdate
from app.features.settings.services import settings_service

USER_ID = "test-user-id"


# ---------------------------------------------------------------------------
# settings_service.get_settings
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_get_settings_returns_defaults_when_no_row(
    mock_db_pool: AsyncMock,
) -> None:
    """get_settings returns default values when no DB row exists."""
    mock_db_pool.fetchrow = AsyncMock(return_value=None)
    mock_db_pool.execute = AsyncMock()

    result = await settings_service.get_settings(USER_ID, mock_db_pool)

    assert isinstance(result, RadioSettingsResponse)
    assert result.station_name == "Tramontane"
    assert result.language == "fr"
    assert result.location == ""


@pytest.mark.unit
async def test_get_settings_returns_row_data(
    mock_db_pool: AsyncMock,
) -> None:
    """get_settings returns data from the DB row when one exists."""
    mock_db_pool.fetchrow = AsyncMock(
        return_value={
            "station_name": "My Radio",
            "language": "en",
            "location": "Paris",
        }
    )

    result = await settings_service.get_settings(USER_ID, mock_db_pool)

    assert result.station_name == "My Radio"
    assert result.language == "en"
    assert result.location == "Paris"


# ---------------------------------------------------------------------------
# settings_service.update_settings
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_update_settings_calls_ensure_and_update(
    mock_db_pool: AsyncMock,
) -> None:
    """update_settings calls ensure_defaults, update, then re-fetches."""
    updated_row = {
        "station_name": "New Name",
        "language": "fr",
        "location": "",
    }
    mock_db_pool.fetchrow = AsyncMock(return_value=updated_row)
    mock_db_pool.execute = AsyncMock()

    data = RadioSettingsUpdate(station_name="New Name")
    result = await settings_service.update_settings(USER_ID, data, mock_db_pool)

    assert result.station_name == "New Name"
    # ensure_defaults + update = at least 2 execute calls
    assert mock_db_pool.execute.await_count >= 2


@pytest.mark.unit
async def test_update_settings_empty_body_returns_current(
    mock_db_pool: AsyncMock,
) -> None:
    """update_settings with no fields set returns current settings without writing."""
    mock_db_pool.fetchrow = AsyncMock(
        return_value={
            "station_name": "Tramontane",
            "language": "fr",
            "location": "",
        }
    )
    mock_db_pool.execute = AsyncMock()

    data = RadioSettingsUpdate()  # nothing set
    result = await settings_service.update_settings(USER_ID, data, mock_db_pool)

    assert result.station_name == "Tramontane"
    # No execute calls when body is empty (no ensure_defaults, no update)
    mock_db_pool.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# settings_repository.get_by_user
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_repo_get_by_user(mock_db_pool: AsyncMock) -> None:
    """get_by_user calls pool.fetchrow with correct SQL."""
    expected = {"station_name": "R", "language": "fr", "location": ""}
    mock_db_pool.fetchrow = AsyncMock(return_value=expected)

    result = await settings_repository.get_by_user(USER_ID, mock_db_pool)

    assert result == expected
    mock_db_pool.fetchrow.assert_awaited_once()
    sql_arg = mock_db_pool.fetchrow.call_args[0][0]
    assert "radio_settings" in sql_arg


# ---------------------------------------------------------------------------
# settings_repository.ensure_defaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_repo_ensure_defaults(mock_db_pool: AsyncMock) -> None:
    """ensure_defaults calls pool.execute with INSERT ... ON CONFLICT."""
    mock_db_pool.execute = AsyncMock()

    await settings_repository.ensure_defaults(USER_ID, mock_db_pool)

    mock_db_pool.execute.assert_awaited_once()
    sql_arg = mock_db_pool.execute.call_args[0][0]
    assert "INSERT" in sql_arg
    assert "ON CONFLICT" in sql_arg


# ---------------------------------------------------------------------------
# settings_repository.update
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_repo_update_builds_set_clause(mock_db_pool: AsyncMock) -> None:
    """update builds a dynamic SET clause from the updates dict."""
    mock_db_pool.execute = AsyncMock()

    await settings_repository.update(
        USER_ID,
        {"station_name": "New", "language": "en"},
        mock_db_pool,
    )

    mock_db_pool.execute.assert_awaited_once()
    sql_arg = mock_db_pool.execute.call_args[0][0]
    assert "UPDATE radio_settings" in sql_arg
    assert "station_name" in sql_arg
    assert "language" in sql_arg
