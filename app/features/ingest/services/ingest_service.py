"""Ingest service — scan music directory, read tags, orchestrate storage."""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg
import structlog

from app.features.ingest.repositories.tag_repository import TagRepository
from app.features.ingest.repositories.track_repository import TrackRepository
from app.features.ingest.schemas.ingest import ScanResult, TrackMetadata
from app.features.ingest.services.metadata_service import read_metadata

logger = structlog.get_logger(__name__)

AUDIO_EXTENSIONS = frozenset({".mp3", ".flac", ".wav", ".ogg"})


def scan_directory(directory: Path) -> list[Path]:
    """Find all audio files recursively in a directory."""
    if not directory.is_dir():
        logger.warning("scan_directory_not_found", directory=str(directory))
        return []

    files = [
        f
        for f in directory.rglob("*")
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
    ]
    files.sort()
    logger.info("scan_directory_complete", directory=str(directory), count=len(files))
    return files


def _read_all_metadata(files: list[Path]) -> list[tuple[TrackMetadata, int]]:
    """Read metadata and file sizes for all audio files (blocking I/O)."""
    results: list[tuple[TrackMetadata, int]] = []
    for f in files:
        try:
            metadata = read_metadata(f)
            file_size = f.stat().st_size
            results.append((metadata, file_size))
        except OSError:
            logger.warning("file_unreadable", path=str(f))
    return results


class IngestService:
    """Orchestrates scanning a directory and persisting tracks + tags."""

    def __init__(
        self,
        track_repo: TrackRepository,
        tag_repo: TagRepository,
    ) -> None:
        self.track_repo = track_repo
        self.tag_repo = tag_repo

    async def scan_and_store(self, directory: Path) -> ScanResult:
        """Scan a directory for audio files, read their tags, and persist."""
        # Run blocking filesystem I/O in thread pool
        files = await asyncio.to_thread(scan_directory, directory)
        tracks_with_sizes = await asyncio.to_thread(_read_all_metadata, files)

        tracks = [track for track, _ in tracks_with_sizes]
        stored = 0
        for track, file_size in tracks_with_sizes:
            try:
                track_id = await self.track_repo.upsert(
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                    duration_seconds=track.duration_seconds,
                    file_path=track.file_path,
                    file_size_bytes=file_size,
                )

                if track.tags:
                    await self.tag_repo.replace_by_source(
                        track_id=track_id,
                        source="id3",
                        tags=[(t.tag, t.category) for t in track.tags],
                    )
            except asyncpg.PostgresError:
                logger.exception("track_store_failed", file_path=track.file_path)
                continue

            stored += 1

        logger.info(
            "scan_and_store_complete",
            directory=str(directory),
            scanned=len(tracks),
            stored=stored,
        )

        return ScanResult(scanned=len(tracks), stored=stored, tracks=tracks)
