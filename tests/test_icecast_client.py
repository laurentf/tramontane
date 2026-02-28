"""Unit tests for Icecast client — now-playing parsing and HTTP interactions."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.features.radio.services.icecast_client import (
    _parse_stream_title,
    get_now_playing,
)


def _make_httpx_response(json_data: dict, *, status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response with sync .json() and .raise_for_status()."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _make_async_client(response: MagicMock) -> MagicMock:
    """Build a mock httpx.AsyncClient that returns the given response from get()."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


class TestParseStreamTitle:
    def test_artist_dash_title(self) -> None:
        title, artist = _parse_stream_title("Led Zeppelin - Stairway to Heaven")
        assert artist == "Led Zeppelin"
        assert title == "Stairway to Heaven"

    def test_html_entities_unescaped(self) -> None:
        title, artist = _parse_stream_title("AC/DC &amp; Friends - T.N.T.")
        assert artist == "AC/DC & Friends"
        assert title == "T.N.T."

    def test_no_separator(self) -> None:
        title, artist = _parse_stream_title("Just A Title")
        assert title == "Just A Title"
        assert artist == "Unknown Artist"

    def test_empty_string(self) -> None:
        title, artist = _parse_stream_title("")
        assert title == "Unknown Track"
        assert artist == "Unknown Artist"

    def test_whitespace_only(self) -> None:
        title, artist = _parse_stream_title("   ")
        assert title == "Unknown Track"
        assert artist == "Unknown Artist"

    def test_multiple_dashes(self) -> None:
        """Only splits on first ' - ', so title may contain hyphens."""
        title, artist = _parse_stream_title("Artist - Title - Part 2")
        assert artist == "Artist"
        assert title == "Title - Part 2"

    def test_empty_artist_after_split(self) -> None:
        title, artist = _parse_stream_title(" - Some Title")
        assert artist == "Unknown Artist"
        assert title == "Some Title"

    def test_empty_title_after_split(self) -> None:
        title, artist = _parse_stream_title("Some Artist - ")
        assert artist == "Some Artist"
        assert title == "Unknown Track"


class TestGetNowPlaying:
    @pytest.mark.unit
    async def test_single_source_dict(self) -> None:
        """Icecast sometimes returns source as a dict instead of a list."""
        icecast_json = {
            "icestats": {
                "source": {
                    "listenurl": "http://icecast:8000/stream.mp3",
                    "title": "Test Artist - Test Song",
                    "genre": "Electronic",
                    "listeners": 5,
                }
            }
        }

        response = _make_httpx_response(icecast_json)
        client = _make_async_client(response)

        with (
            patch(
                "app.features.radio.services.icecast_client._get_icecast_url",
                return_value="http://icecast:8000",
            ),
            patch(
                "app.features.radio.services.icecast_client.httpx.AsyncClient",
                return_value=client,
            ),
        ):
            result = await get_now_playing()

        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.genre == "Electronic"
        assert result.listeners == 5

    @pytest.mark.unit
    async def test_source_list(self) -> None:
        """Icecast with multiple mounts returns source as a list."""
        icecast_json = {
            "icestats": {
                "source": [
                    {
                        "listenurl": "http://icecast:8000/other.mp3",
                        "title": "Other",
                    },
                    {
                        "listenurl": "http://icecast:8000/stream.mp3",
                        "title": "Right Artist - Right Song",
                        "listeners": "3",
                    },
                ]
            }
        }

        response = _make_httpx_response(icecast_json)
        client = _make_async_client(response)

        with (
            patch(
                "app.features.radio.services.icecast_client._get_icecast_url",
                return_value="http://icecast:8000",
            ),
            patch(
                "app.features.radio.services.icecast_client.httpx.AsyncClient",
                return_value=client,
            ),
        ):
            result = await get_now_playing()

        assert result.title == "Right Song"
        assert result.artist == "Right Artist"
        assert result.listeners == 3

    @pytest.mark.unit
    async def test_mount_not_found(self) -> None:
        """Returns defaults when /stream.mp3 mount is not present."""
        icecast_json = {
            "icestats": {
                "source": [
                    {"listenurl": "http://icecast:8000/other.mp3", "title": "X"}
                ]
            }
        }

        response = _make_httpx_response(icecast_json)
        client = _make_async_client(response)

        with (
            patch(
                "app.features.radio.services.icecast_client._get_icecast_url",
                return_value="http://icecast:8000",
            ),
            patch(
                "app.features.radio.services.icecast_client.httpx.AsyncClient",
                return_value=client,
            ),
        ):
            result = await get_now_playing()

        assert result.title == "Unknown Track"
        assert result.artist == "Unknown Artist"

    @pytest.mark.unit
    async def test_connection_error_returns_defaults(self) -> None:
        client = AsyncMock()
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "app.features.radio.services.icecast_client._get_icecast_url",
                return_value="http://icecast:8000",
            ),
            patch(
                "app.features.radio.services.icecast_client.httpx.AsyncClient",
                return_value=client,
            ),
        ):
            result = await get_now_playing()

        assert result.title == "Unknown Track"
        assert result.listeners == 0

    @pytest.mark.unit
    async def test_http_error_returns_defaults(self) -> None:
        request = httpx.Request("GET", "http://icecast:8000/status-json.xsl")
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=request, response=mock_response
        )

        client = _make_async_client(mock_response)

        with (
            patch(
                "app.features.radio.services.icecast_client._get_icecast_url",
                return_value="http://icecast:8000",
            ),
            patch(
                "app.features.radio.services.icecast_client.httpx.AsyncClient",
                return_value=client,
            ),
        ):
            result = await get_now_playing()

        assert result.title == "Unknown Track"

    @pytest.mark.unit
    async def test_invalid_listener_count(self) -> None:
        """Non-numeric listener count falls back to 0."""
        icecast_json = {
            "icestats": {
                "source": {
                    "listenurl": "http://icecast:8000/stream.mp3",
                    "title": "A - B",
                    "listeners": "not-a-number",
                }
            }
        }

        response = _make_httpx_response(icecast_json)
        client = _make_async_client(response)

        with (
            patch(
                "app.features.radio.services.icecast_client._get_icecast_url",
                return_value="http://icecast:8000",
            ),
            patch(
                "app.features.radio.services.icecast_client.httpx.AsyncClient",
                return_value=client,
            ),
        ):
            result = await get_now_playing()

        assert result.listeners == 0
