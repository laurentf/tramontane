"""Play history repository for rolling-window repeat avoidance.

Records and queries track plays per block/host to prevent repetition.
"""

import structlog

logger = structlog.get_logger(__name__)


class PlayHistoryRepository:
    """Repository for play_history table operations.

    Used by the music selector to avoid repeating tracks within a rolling window.
    """

    def __init__(self, pool) -> None:
        """Initialize with an asyncpg connection pool."""
        self._pool = pool

    async def record_play(
        self,
        track_id: str,
        block_id: str | None = None,
        host_id: str | None = None,
    ) -> None:
        """Record a track play in the history.

        Args:
            track_id: UUID of the track played.
            block_id: UUID of the schedule block (optional).
            host_id: UUID of the host (optional).
        """
        async with self._pool.acquire(timeout=10) as conn:
            await conn.execute(
                """
                INSERT INTO play_history (track_id, block_id, host_id)
                VALUES ($1, $2, $3)
                """,
                track_id,
                block_id,
                host_id,
            )
        logger.info(
            "play_history.recorded",
            track_id=track_id,
            block_id=block_id,
            host_id=host_id,
        )

    async def get_recent_track_ids(
        self,
        *,
        host_id: str | None = None,
        limit: int = 20,
    ) -> list[str]:
        """Get recently played track IDs for repeat avoidance.

        Args:
            host_id: Filter by host (optional).
            limit: Maximum number of recent track IDs to return.

        Returns:
            List of track ID strings, most recent first.
        """
        async with self._pool.acquire(timeout=10) as conn:
            if host_id:
                rows = await conn.fetch(
                    """
                    SELECT track_id
                    FROM play_history
                    WHERE host_id = $1
                    GROUP BY track_id
                    ORDER BY MAX(played_at) DESC
                    LIMIT $2
                    """,
                    host_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT track_id
                    FROM play_history
                    GROUP BY track_id
                    ORDER BY MAX(played_at) DESC
                    LIMIT $1
                    """,
                    limit,
                )
        return [str(row["track_id"]) for row in rows]

    async def get_play_count_since(
        self,
        track_id: str,
        since_hours: int = 24,
    ) -> int:
        """Count how many times a track has been played in the last N hours.

        Args:
            track_id: UUID of the track.
            since_hours: Look-back window in hours.

        Returns:
            Number of plays.
        """
        async with self._pool.acquire(timeout=10) as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM play_history
                WHERE track_id = $1
                  AND played_at > NOW() - INTERVAL '1 hour' * $2
                """,
                track_id,
                since_hours,
            )
        return count or 0
