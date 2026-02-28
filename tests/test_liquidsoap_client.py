"""Unit tests for Liquidsoap client — track push via Harbor HTTP."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.features.radio.services.liquidsoap_client import push_track


def _make_async_client(
    response: MagicMock | None = None, *, side_effect: Exception | None = None
) -> AsyncMock:
    """Build a mock httpx.AsyncClient context manager."""
    client = AsyncMock()
    if side_effect:
        client.post = AsyncMock(side_effect=side_effect)
    else:
        client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.mark.unit
async def test_push_track_success() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"status": "ok", "result": "queued"}

    client = _make_async_client(resp)

    with (
        patch(
            "app.features.radio.services.liquidsoap_client._get_harbor_url",
            return_value="http://liquidsoap:8080",
        ),
        patch(
            "app.features.radio.services.liquidsoap_client.httpx.AsyncClient",
            return_value=client,
        ),
    ):
        result = await push_track("/music/song.mp3")

    assert result["status"] == "ok"
    client.post.assert_called_once_with(
        "http://liquidsoap:8080/push",
        content="/music/song.mp3",
        headers={"Content-Type": "text/plain"},
    )


@pytest.mark.unit
async def test_push_track_connection_error() -> None:
    client = _make_async_client(side_effect=httpx.ConnectError("refused"))

    with (
        patch(
            "app.features.radio.services.liquidsoap_client._get_harbor_url",
            return_value="http://liquidsoap:8080",
        ),
        patch(
            "app.features.radio.services.liquidsoap_client.httpx.AsyncClient",
            return_value=client,
        ),
    ):
        result = await push_track("/music/song.mp3")

    assert result["status"] == "error"
    assert "Cannot connect" in result["message"]


@pytest.mark.unit
async def test_push_track_http_status_error() -> None:
    request = httpx.Request("POST", "http://liquidsoap:8080/push")
    resp = MagicMock()
    resp.status_code = 500
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=request, response=resp
    )

    client = _make_async_client(resp)

    with (
        patch(
            "app.features.radio.services.liquidsoap_client._get_harbor_url",
            return_value="http://liquidsoap:8080",
        ),
        patch(
            "app.features.radio.services.liquidsoap_client.httpx.AsyncClient",
            return_value=client,
        ),
    ):
        result = await push_track("/music/song.mp3")

    assert result["status"] == "error"
    assert "500" in result["message"]


@pytest.mark.unit
async def test_push_track_generic_http_error() -> None:
    client = _make_async_client(side_effect=httpx.ReadTimeout("timeout"))

    with (
        patch(
            "app.features.radio.services.liquidsoap_client._get_harbor_url",
            return_value="http://liquidsoap:8080",
        ),
        patch(
            "app.features.radio.services.liquidsoap_client.httpx.AsyncClient",
            return_value=client,
        ),
    ):
        result = await push_track("/music/song.mp3")

    assert result["status"] == "error"
    assert "Failed to push" in result["message"]
