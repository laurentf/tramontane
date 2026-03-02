"""Track data access layer — asyncpg queries for the tracks table."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from uuid import UUID

import asyncpg


class TrackRow(TypedDict):
    """Shape of a row from the tracks table."""

    id: UUID
    title: str
    artist: str
    album: str | None
    duration_seconds: float | None
    file_path: str
    file_size_bytes: int | None
    play_count: int
    last_played_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TrackRepository:
    """Repository for tracks table operations."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def upsert(
        self,
        *,
        title: str,
        artist: str,
        album: str | None,
        duration_seconds: float | None,
        file_path: str,
        file_size_bytes: int | None,
    ) -> UUID:
        """Insert or update a track by file_path. Returns the track id."""
        async with self.pool.acquire(timeout=10) as conn:
            track_id: UUID = await conn.fetchval(
                """
                INSERT INTO tracks
                    (title, artist, album, duration_seconds, file_path, file_size_bytes)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (file_path) DO UPDATE SET
                    title = EXCLUDED.title,
                    artist = EXCLUDED.artist,
                    album = EXCLUDED.album,
                    duration_seconds = EXCLUDED.duration_seconds,
                    file_size_bytes = EXCLUDED.file_size_bytes,
                    updated_at = NOW()
                RETURNING id
                """,
                title,
                artist,
                album,
                duration_seconds,
                file_path,
                file_size_bytes,
            )
        return track_id

    async def get_by_id(self, track_id: str | UUID) -> TrackRow | None:
        """Look up a track by its ID."""
        async with self.pool.acquire(timeout=10) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tracks WHERE id = $1",
                UUID(str(track_id)),
            )
        return dict(row) if row else None  # type: ignore[return-value]

    async def get_by_file_path(self, file_path: str) -> TrackRow | None:
        """Look up a track by its file path."""
        async with self.pool.acquire(timeout=10) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tracks WHERE file_path = $1",
                file_path,
            )
        return dict(row) if row else None  # type: ignore[return-value]

    async def list_all(self, *, limit: int = 200, offset: int = 0) -> list[TrackRow]:
        """List tracks ordered by title."""
        async with self.pool.acquire(timeout=10) as conn:
            rows = await conn.fetch(
                "SELECT * FROM tracks ORDER BY title LIMIT $1 OFFSET $2",
                limit,
                offset,
            )
        return [dict(r) for r in rows]  # type: ignore[misc]
