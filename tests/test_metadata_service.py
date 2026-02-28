"""Unit tests for metadata extraction service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.features.ingest.services.metadata_service import (
    _first_or_default,
    read_metadata,
)


class TestFirstOrDefault:
    def test_returns_first_value(self) -> None:
        assert _first_or_default(["hello", "world"], "default") == "hello"

    def test_returns_default_on_none(self) -> None:
        assert _first_or_default(None, "default") == "default"

    def test_returns_default_on_empty_list(self) -> None:
        assert _first_or_default([], "default") == "default"

    def test_returns_default_on_empty_string(self) -> None:
        assert _first_or_default([""], "default") == "default"

    def test_returns_none_default(self) -> None:
        assert _first_or_default([], None) is None


class TestReadMetadata:
    def test_mp3_with_tags(self) -> None:
        mock_info = MagicMock()
        mock_info.length = 180.5

        mock_mp3 = MagicMock()
        mock_mp3.info = mock_info

        mock_id3_data = {
            "title": ["Test Song"],
            "artist": ["Test Artist"],
            "album": ["Test Album"],
            "genre": ["Rock;Blues"],
            "mood": ["chill"],
        }

        with (
            patch(
                "app.features.ingest.services.metadata_service.MP3",
                return_value=mock_mp3,
            ),
            patch(
                "app.features.ingest.services.metadata_service.EasyID3",
                return_value=mock_id3_data,
            ),
        ):
            result = read_metadata(Path("/music/test.mp3"))

        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.album == "Test Album"
        assert result.duration_seconds == 180.5
        assert result.file_path == "/music/test.mp3"
        # genre "Rock;Blues" should split into two genre tags
        genre_tags = [t for t in result.tags if t.category == "genre"]
        assert len(genre_tags) == 2
        assert genre_tags[0].tag == "rock"
        assert genre_tags[1].tag == "blues"
        # mood tag
        mood_tags = [t for t in result.tags if t.category == "mood"]
        assert len(mood_tags) == 1
        assert mood_tags[0].tag == "chill"

    def test_mp3_no_id3_header(self) -> None:
        from mutagen.id3 import ID3NoHeaderError

        mock_info = MagicMock()
        mock_info.length = 120.0
        mock_mp3 = MagicMock()
        mock_mp3.info = mock_info

        with (
            patch(
                "app.features.ingest.services.metadata_service.MP3",
                return_value=mock_mp3,
            ),
            patch(
                "app.features.ingest.services.metadata_service.EasyID3",
                side_effect=ID3NoHeaderError("no header"),
            ),
        ):
            result = read_metadata(Path("/music/notags.mp3"))

        assert result.title == "Unknown Title"
        assert result.artist == "Unknown Artist"
        assert result.duration_seconds == 120.0

    def test_flac_with_tags(self) -> None:
        mock_info = MagicMock()
        mock_info.length = 240.0
        mock_tags = {"title": ["Flac Song"], "artist": ["Flac Artist"], "genre": ["Jazz"]}

        mock_flac = MagicMock()
        mock_flac.info = mock_info
        mock_flac.tags = mock_tags

        with patch(
            "app.features.ingest.services.metadata_service.FLAC",
            return_value=mock_flac,
        ):
            result = read_metadata(Path("/music/test.flac"))

        assert result.title == "Flac Song"
        assert result.artist == "Flac Artist"
        assert result.duration_seconds == 240.0
        assert any(t.tag == "jazz" for t in result.tags)

    def test_ogg_with_tags(self) -> None:
        mock_info = MagicMock()
        mock_info.length = 300.0

        mock_ogg = MagicMock()
        mock_ogg.info = mock_info
        mock_ogg.__bool__ = lambda self: True
        mock_ogg.__iter__ = lambda self: iter(["title", "artist"])
        mock_ogg.__getitem__ = lambda self, key: {
            "title": ["Ogg Song"],
            "artist": ["Ogg Artist"],
        }[key]
        mock_ogg.get = lambda key, default=None: {
            "title": ["Ogg Song"],
            "artist": ["Ogg Artist"],
        }.get(key, default)
        # dict(ogg) needs keys() and __getitem__
        mock_ogg.keys = lambda: ["title", "artist"]

        with patch(
            "app.features.ingest.services.metadata_service.OggVorbis",
            return_value=mock_ogg,
        ):
            result = read_metadata(Path("/music/test.ogg"))

        assert result.title == "Ogg Song"
        assert result.artist == "Ogg Artist"
        assert result.duration_seconds == 300.0

    def test_unsupported_format(self) -> None:
        result = read_metadata(Path("/music/test.wav"))

        assert result.title == "Unknown Title"
        assert result.artist == "Unknown Artist"
        assert result.duration_seconds is None
        assert result.tags == []

    def test_mutagen_exception_handled(self) -> None:
        from mutagen import MutagenError

        with patch(
            "app.features.ingest.services.metadata_service.MP3",
            side_effect=MutagenError("corrupted file"),
        ):
            result = read_metadata(Path("/music/corrupt.mp3"))

        assert result.title == "Unknown Title"
        assert result.artist == "Unknown Artist"

    @pytest.mark.parametrize(
        ("genre_str", "expected"),
        [
            ("Rock", ["rock"]),
            ("Rock;Blues;Jazz", ["rock", "blues", "jazz"]),
            (";", []),
            ("", []),
        ],
    )
    def test_genre_splitting(self, genre_str: str, expected: list[str]) -> None:
        mock_info = MagicMock()
        mock_info.length = 100.0
        mock_mp3 = MagicMock()
        mock_mp3.info = mock_info

        with (
            patch(
                "app.features.ingest.services.metadata_service.MP3",
                return_value=mock_mp3,
            ),
            patch(
                "app.features.ingest.services.metadata_service.EasyID3",
                return_value={"genre": [genre_str]},
            ),
        ):
            result = read_metadata(Path("/music/test.mp3"))

        genre_tags = [t.tag for t in result.tags if t.category == "genre"]
        assert genre_tags == expected
