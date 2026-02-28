"""Tag data access layer — asyncpg queries for the track_tags table."""

from __future__ import annotations

from uuid import UUID

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


class TagRepository:
    """Repository for track_tags table operations."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def replace_by_source(
        self,
        track_id: UUID,
        source: str,
        tags: list[tuple[str, str]],
    ) -> None:
        """Replace all tags for a track from a given source.

        Deletes existing tags with the given source, then inserts the new ones.
        Each tag tuple is (tag_value, category).
        """
        async with self.pool.acquire(timeout=10) as conn, conn.transaction():
            await conn.execute(
                "DELETE FROM track_tags WHERE track_id = $1 AND source = $2",
                track_id,
                source,
            )
            if tags:
                await conn.executemany(
                    """
                    INSERT INTO track_tags (track_id, tag, category, source)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (track_id, tag, category) DO NOTHING
                    """,
                    [(track_id, tag, category, source) for tag, category in tags],
                )

    async def get_by_track(self, track_id: UUID) -> list[dict]:
        """Get all tags for a track."""
        async with self.pool.acquire(timeout=10) as conn:
            rows = await conn.fetch(
                """
                SELECT tag, category, source, created_at
                FROM track_tags WHERE track_id = $1
                ORDER BY category, tag
                """,
                track_id,
            )
        return [dict(r) for r in rows]

    async def find_tracks_by_tag(self, tag: str, *, limit: int = 50) -> list[UUID]:
        """Find track IDs that have a given tag."""
        async with self.pool.acquire(timeout=10) as conn:
            rows = await conn.fetch(
                "SELECT track_id FROM track_tags WHERE tag = $1 LIMIT $2",
                tag,
                limit,
            )
        return [r["track_id"] for r in rows]
