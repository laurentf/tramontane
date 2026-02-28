"""Unit tests for ingest service — directory scanning and orchestration."""

from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import asyncpg
import pytest

from app.features.ingest.schemas.ingest import TrackMetadata, TrackTag
from app.features.ingest.services.ingest_service import (
    AUDIO_EXTENSIONS,
    IngestService,
    _read_all_metadata,
    scan_directory,
)


class TestScanDirectory:
    def test_finds_audio_files(self, tmp_path: Path) -> None:
        (tmp_path / "song.mp3").touch()
        (tmp_path / "song.flac").touch()
        (tmp_path / "song.ogg").touch()
        (tmp_path / "song.wav").touch()
        (tmp_path / "readme.txt").touch()
        (tmp_path / "cover.jpg").touch()

        result = scan_directory(tmp_path)

        assert len(result) == 4
        extensions = {f.suffix.lower() for f in result}
        assert extensions == {".mp3", ".flac", ".ogg", ".wav"}

    def test_recursive_scan(self, tmp_path: Path) -> None:
        sub = tmp_path / "artist" / "album"
        sub.mkdir(parents=True)
        (sub / "track.mp3").touch()
        (tmp_path / "top.flac").touch()

        result = scan_directory(tmp_path)
        assert len(result) == 2

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        result = scan_directory(tmp_path / "nonexistent")
        assert result == []

    def test_empty_directory(self, tmp_path: Path) -> None:
        result = scan_directory(tmp_path)
        assert result == []

    def test_results_sorted(self, tmp_path: Path) -> None:
        (tmp_path / "c.mp3").touch()
        (tmp_path / "a.mp3").touch()
        (tmp_path / "b.mp3").touch()

        result = scan_directory(tmp_path)
        names = [f.name for f in result]
        assert names == ["a.mp3", "b.mp3", "c.mp3"]

    def test_case_insensitive_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "song.MP3").touch()
        (tmp_path / "song.Flac").touch()

        result = scan_directory(tmp_path)
        assert len(result) == 2

    def test_audio_extensions_frozen(self) -> None:
        assert isinstance(AUDIO_EXTENSIONS, frozenset)
        assert ".mp3" in AUDIO_EXTENSIONS


class TestReadAllMetadata:
    def test_reads_metadata_for_files(self, tmp_path: Path) -> None:
        f = tmp_path / "test.mp3"
        f.write_bytes(b"fake audio content")

        mock_meta = TrackMetadata(file_path=str(f), title="T", artist="A")

        with patch(
            "app.features.ingest.services.ingest_service.read_metadata",
            return_value=mock_meta,
        ):
            results = _read_all_metadata([f])

        assert len(results) == 1
        meta, size = results[0]
        assert meta.title == "T"
        assert size == f.stat().st_size

    def test_skips_unreadable_files(self) -> None:
        bad_path = Path("/nonexistent/bad.mp3")

        with patch(
            "app.features.ingest.services.ingest_service.read_metadata",
            side_effect=OSError("file gone"),
        ):
            results = _read_all_metadata([bad_path])

        assert results == []


class TestIngestService:
    @pytest.fixture
    def track_repo(self) -> AsyncMock:
        repo = AsyncMock()
        repo.upsert = AsyncMock(return_value=uuid4())
        return repo

    @pytest.fixture
    def tag_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def service(self, track_repo: AsyncMock, tag_repo: AsyncMock) -> IngestService:
        return IngestService(track_repo=track_repo, tag_repo=tag_repo)

    @pytest.mark.unit
    async def test_scan_and_store_empty_dir(
        self, service: IngestService, track_repo: AsyncMock
    ) -> None:
        with patch(
            "app.features.ingest.services.ingest_service.scan_directory",
            return_value=[],
        ):
            result = await service.scan_and_store(Path("/music"))

        assert result.scanned == 0
        assert result.stored == 0
        track_repo.upsert.assert_not_called()

    @pytest.mark.unit
    async def test_scan_and_store_with_tracks(
        self, service: IngestService, track_repo: AsyncMock, tag_repo: AsyncMock
    ) -> None:
        track_id = uuid4()
        track_repo.upsert = AsyncMock(return_value=track_id)

        meta = TrackMetadata(
            file_path="/music/song.mp3",
            title="Song",
            artist="Artist",
            tags=[TrackTag(tag="rock", category="genre", source="id3")],
        )

        with (
            patch(
                "app.features.ingest.services.ingest_service.scan_directory",
                return_value=[Path("/music/song.mp3")],
            ),
            patch(
                "app.features.ingest.services.ingest_service._read_all_metadata",
                return_value=[(meta, 1024)],
            ),
        ):
            result = await service.scan_and_store(Path("/music"))

        assert result.scanned == 1
        assert result.stored == 1
        track_repo.upsert.assert_called_once()
        tag_repo.replace_by_source.assert_called_once_with(
            track_id=track_id,
            source="id3",
            tags=[("rock", "genre")],
        )

    @pytest.mark.unit
    async def test_scan_and_store_no_tags(
        self, service: IngestService, tag_repo: AsyncMock
    ) -> None:
        meta = TrackMetadata(
            file_path="/music/notags.mp3", title="No Tags", artist="Artist"
        )

        with (
            patch(
                "app.features.ingest.services.ingest_service.scan_directory",
                return_value=[Path("/music/notags.mp3")],
            ),
            patch(
                "app.features.ingest.services.ingest_service._read_all_metadata",
                return_value=[(meta, 512)],
            ),
        ):
            result = await service.scan_and_store(Path("/music"))

        assert result.stored == 1
        tag_repo.replace_by_source.assert_not_called()

    @pytest.mark.unit
    async def test_scan_and_store_db_error_skips_track(
        self, service: IngestService, track_repo: AsyncMock
    ) -> None:
        """A PostgresError on one track should not abort the entire scan."""
        track_repo.upsert = AsyncMock(
            side_effect=asyncpg.UniqueViolationError("duplicate")
        )

        meta = TrackMetadata(
            file_path="/music/dup.mp3", title="Dup", artist="Artist"
        )

        with (
            patch(
                "app.features.ingest.services.ingest_service.scan_directory",
                return_value=[Path("/music/dup.mp3")],
            ),
            patch(
                "app.features.ingest.services.ingest_service._read_all_metadata",
                return_value=[(meta, 256)],
            ),
        ):
            result = await service.scan_and_store(Path("/music"))

        assert result.scanned == 1
        assert result.stored == 0

    @pytest.mark.unit
    async def test_scan_and_store_multiple_tracks(
        self, service: IngestService, track_repo: AsyncMock
    ) -> None:
        ids = [uuid4(), uuid4(), uuid4()]
        track_repo.upsert = AsyncMock(side_effect=ids)

        tracks = [
            (TrackMetadata(file_path=f"/music/{i}.mp3", title=f"S{i}", artist="A"), 100)
            for i in range(3)
        ]

        with (
            patch(
                "app.features.ingest.services.ingest_service.scan_directory",
                return_value=[Path(f"/music/{i}.mp3") for i in range(3)],
            ),
            patch(
                "app.features.ingest.services.ingest_service._read_all_metadata",
                return_value=tracks,
            ),
        ):
            result = await service.scan_and_store(Path("/music"))

        assert result.scanned == 3
        assert result.stored == 3
        assert track_repo.upsert.call_count == 3
