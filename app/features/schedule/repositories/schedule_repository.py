"""Schedule block data access layer -- asyncpg queries for the schedule_blocks table."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


_UPDATABLE_COLUMNS = frozenset({
    "host_id", "name", "description", "start_time",
    "end_time", "day_of_week", "is_active",
})


class ScheduleRepository:
    """Repository for schedule_blocks table operations."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        *,
        user_id: str,
        host_id: str,
        name: str,
        description: str,
        start_time: str,
        end_time: str,
        day_of_week: int | None,
        is_active: bool,
    ) -> str:
        """Insert a new schedule block. Returns the block ID."""
        async with self.pool.acquire(timeout=10) as conn:
            block_id: str = str(
                await conn.fetchval(
                    """
                    INSERT INTO schedule_blocks
                        (user_id, host_id, name, description, start_time,
                         end_time, day_of_week, is_active)
                    VALUES ($1, $2::uuid, $3, $4, $5::text::time, $6::text::time, $7, $8)
                    RETURNING id
                    """,
                    user_id,
                    host_id,
                    name,
                    description,
                    start_time,
                    end_time,
                    day_of_week,
                    is_active,
                )
            )
        return block_id

    async def get_by_id(self, block_id: str, user_id: str) -> dict | None:
        """Get a single schedule block by ID with host info, scoped to user."""
        async with self.pool.acquire(timeout=10) as conn:
            row = await conn.fetchrow(
                """
                SELECT sb.*, h.name AS host_name, h.avatar_url AS host_avatar_url,
                       h.template_id AS host_template_id
                FROM schedule_blocks sb
                LEFT JOIN hosts h ON sb.host_id = h.id
                WHERE sb.id = $1 AND sb.user_id = $2
                """,
                block_id,
                user_id,
            )
        return dict(row) if row else None

    async def list_by_user(self, user_id: str) -> list[dict]:
        """List all schedule blocks for a user with host info, ordered by start_time."""
        async with self.pool.acquire(timeout=10) as conn:
            rows = await conn.fetch(
                """
                SELECT sb.*, h.name AS host_name, h.avatar_url AS host_avatar_url,
                       h.template_id AS host_template_id
                FROM schedule_blocks sb
                LEFT JOIN hosts h ON sb.host_id = h.id
                WHERE sb.user_id = $1
                ORDER BY sb.start_time ASC
                """,
                user_id,
            )
        return [dict(r) for r in rows]

    async def update(
        self, block_id: str, user_id: str, **fields: str | int | bool | None,
    ) -> dict | None:
        """Update schedule block fields dynamically. Returns updated row or None."""
        if not fields:
            return await self.get_by_id(block_id, user_id)

        # Validate column names against whitelist to prevent SQL injection.
        for key in fields:
            if key not in _UPDATABLE_COLUMNS:
                raise ValueError(f"Invalid column: {key}")

        set_parts: list[str] = []
        values: list[str | int | bool | None] = []
        idx = 1

        for key, value in fields.items():
            if key in ("start_time", "end_time") and value is not None:
                set_parts.append(f"{key} = ${idx}::text::time")
            else:
                set_parts.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1

        set_parts.append("updated_at = NOW()")
        set_clause = ", ".join(set_parts)

        values.append(block_id)
        values.append(user_id)

        query = f"""
            UPDATE schedule_blocks SET {set_clause}
            WHERE id = ${idx} AND user_id = ${idx + 1}
            RETURNING *
        """

        async with self.pool.acquire(timeout=10) as conn:
            row = await conn.fetchrow(query, *values)

        if row is None:
            return None

        # Re-fetch with host join for consistent response
        return await self.get_by_id(block_id, user_id)

    async def delete(self, block_id: str, user_id: str) -> bool:
        """Delete a schedule block. Returns True if a row was deleted."""
        async with self.pool.acquire(timeout=10) as conn:
            result = await conn.execute(
                "DELETE FROM schedule_blocks WHERE id = $1 AND user_id = $2",
                block_id,
                user_id,
            )
        return result == "DELETE 1"

    async def check_overlap(
        self,
        start_time: str,
        end_time: str,
        day_of_week: int | None,
        *,
        exclude_id: str | None = None,
        user_id: str,
    ) -> bool:
        """Check if a proposed time slot overlaps with existing blocks.

        Handles midnight-crossing blocks for both the proposed and existing slots.
        Returns True if an overlap exists.
        """
        async with self.pool.acquire(timeout=10) as conn:
            has_overlap = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM schedule_blocks sb
                    WHERE sb.user_id = $1
                    AND sb.id != COALESCE($2, '00000000-0000-0000-0000-000000000000'::uuid)
                    AND (sb.day_of_week IS NULL OR $3::int IS NULL OR sb.day_of_week = $3::int)
                    AND NOT (
                        CASE WHEN $4::text::time < $5::text::time
                            THEN $5::text::time <= sb.start_time OR $4::text::time >= sb.end_time
                            ELSE $5::text::time <= sb.start_time AND $4::text::time >= sb.end_time
                        END
                        AND
                        CASE WHEN sb.start_time < sb.end_time
                            THEN sb.end_time <= $4::text::time OR sb.start_time >= $5::text::time
                            ELSE sb.end_time <= $4::text::time AND sb.start_time >= $5::text::time
                        END
                    )
                ) AS has_overlap
                """,
                user_id,
                exclude_id,
                day_of_week,
                start_time,
                end_time,
            )
        return bool(has_overlap)

    async def get_by_id_unscoped(self, block_id: str) -> dict | None:
        """Get a schedule block by ID without user scope (for worker tasks).

        Used by ARQ workers that don't have user context.
        """
        async with self.pool.acquire(timeout=10) as conn:
            row = await conn.fetchrow(
                """
                SELECT sb.*, h.name AS host_name, h.avatar_url AS host_avatar_url,
                       h.template_id AS host_template_id
                FROM schedule_blocks sb
                LEFT JOIN hosts h ON sb.host_id = h.id
                WHERE sb.id = $1
                """,
                block_id,
            )
        return dict(row) if row else None

    async def get_upcoming_blocks(self, within_seconds: int = 60) -> list[dict]:
        """Find blocks starting within the next N seconds.

        Used for pre-generating content ahead of block start.
        """
        async with self.pool.acquire(timeout=10) as conn:
            rows = await conn.fetch(
                """
                SELECT sb.*, h.name AS host_name, h.avatar_url AS host_avatar_url,
                       h.template_id AS host_template_id
                FROM schedule_blocks sb
                LEFT JOIN hosts h ON sb.host_id = h.id
                WHERE sb.is_active = true
                AND (sb.day_of_week IS NULL OR sb.day_of_week = EXTRACT(DOW FROM NOW())::int)
                AND sb.start_time > NOW()::time
                AND sb.start_time <= (NOW() + INTERVAL '1 second' * $1)::time
                ORDER BY sb.start_time ASC
                """,
                within_seconds,
            )
        return [dict(r) for r in rows]

    async def get_active_block(self) -> dict | None:
        """Find the schedule block active right now based on server time.

        Handles midnight-crossing blocks (e.g. 23:00-01:00) by switching
        the time comparison logic when start_time >= end_time.
        """
        async with self.pool.acquire(timeout=10) as conn:
            row = await conn.fetchrow(
                """
                SELECT sb.*, h.name AS host_name, h.avatar_url AS host_avatar_url,
                       h.template_id AS host_template_id
                FROM schedule_blocks sb
                LEFT JOIN hosts h ON sb.host_id = h.id
                WHERE sb.is_active = true
                AND (sb.day_of_week IS NULL OR sb.day_of_week = EXTRACT(DOW FROM NOW())::int)
                AND (
                    CASE WHEN sb.start_time < sb.end_time
                        THEN sb.start_time <= NOW()::time AND sb.end_time > NOW()::time
                        ELSE sb.start_time <= NOW()::time OR sb.end_time > NOW()::time
                    END
                )
                ORDER BY sb.start_time DESC
                LIMIT 1
                """,
            )
        return dict(row) if row else None

    async def get_next_block(self, after_time: str) -> dict | None:
        """Find the next active block starting at or after *after_time*.

        Used for closing prompts ("I pass to {next_host}").
        """
        async with self.pool.acquire(timeout=10) as conn:
            row = await conn.fetchrow(
                """
                SELECT sb.*, h.name AS host_name, h.avatar_url AS host_avatar_url,
                       h.template_id AS host_template_id
                FROM schedule_blocks sb
                LEFT JOIN hosts h ON sb.host_id = h.id
                WHERE sb.is_active = true
                AND (sb.day_of_week IS NULL OR sb.day_of_week = EXTRACT(DOW FROM NOW())::int)
                AND sb.start_time >= $1::text::time
                ORDER BY sb.start_time ASC
                LIMIT 1
                """,
                after_time,
            )
        return dict(row) if row else None

    async def get_previous_block(self, before_time: str) -> dict | None:
        """Find the most recent active block ending at or before *before_time*.

        Used for opening prompts ("taking over from {prev_host}").
        """
        async with self.pool.acquire(timeout=10) as conn:
            row = await conn.fetchrow(
                """
                SELECT sb.*, h.name AS host_name, h.avatar_url AS host_avatar_url,
                       h.template_id AS host_template_id
                FROM schedule_blocks sb
                LEFT JOIN hosts h ON sb.host_id = h.id
                WHERE sb.is_active = true
                AND (sb.day_of_week IS NULL OR sb.day_of_week = EXTRACT(DOW FROM NOW())::int)
                AND sb.end_time <= $1::text::time
                ORDER BY sb.end_time DESC
                LIMIT 1
                """,
                before_time,
            )
        return dict(row) if row else None
