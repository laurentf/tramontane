"""Host data access layer -- asyncpg queries for the hosts table."""

from __future__ import annotations

import json

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


_UPDATABLE_COLUMNS = frozenset({
    "name", "status", "description", "voice_id",
    "avatar_url", "avatar_status", "avatar_prompt",
    "avatar_generation_id",
})


class HostRepository:
    """Repository for hosts table operations."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        *,
        user_id: str,
        name: str,
        template_id: str,
        description: dict | None = None,
        voice_id: str | None = None,
        status: str = "active",
    ) -> str:
        """Insert a new host record. Returns the host ID."""
        description_json = json.dumps(description or {})

        async with self.pool.acquire(timeout=10) as conn:
            host_id: str = str(
                await conn.fetchval(
                    """
                    INSERT INTO hosts
                        (user_id, name, template_id, description,
                         voice_id, status)
                    VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                    RETURNING id
                    """,
                    user_id,
                    name,
                    template_id,
                    description_json,
                    voice_id,
                    status,
                )
            )
        return host_id

    async def get_by_id(self, host_id: str, user_id: str) -> dict | None:
        """Get a single host by ID, scoped to user."""
        async with self.pool.acquire(timeout=10) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM hosts WHERE id = $1 AND user_id = $2",
                host_id,
                user_id,
            )
        return dict(row) if row else None

    async def get_by_id_unscoped(self, host_id: str) -> dict | None:
        """Get a host by ID without user scope (for worker tasks)."""
        async with self.pool.acquire(timeout=10) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM hosts WHERE id = $1",
                host_id,
            )
        return dict(row) if row else None

    async def list_by_user(self, user_id: str) -> list[dict]:
        """List all hosts for a user, newest first."""
        async with self.pool.acquire(timeout=10) as conn:
            rows = await conn.fetch(
                "SELECT * FROM hosts WHERE user_id = $1 ORDER BY created_at DESC",
                user_id,
            )
        return [dict(r) for r in rows]

    async def list_all(self) -> list[dict]:
        """List all hosts across users, newest first."""
        async with self.pool.acquire(timeout=10) as conn:
            rows = await conn.fetch(
                "SELECT * FROM hosts ORDER BY created_at DESC",
            )
        return [dict(r) for r in rows]

    async def update(
        self, host_id: str, user_id: str, **fields: str | int | bool | None,
    ) -> dict | None:
        """Update host fields dynamically. Returns updated row or None."""
        if not fields:
            return await self.get_by_id(host_id, user_id)

        # Validate column names against whitelist to prevent SQL injection.
        for key in fields:
            if key not in _UPDATABLE_COLUMNS:
                raise ValueError(f"Invalid column: {key}")

        # Build SET clause dynamically from provided kwargs
        set_parts: list[str] = []
        values: list[str | int | bool | None] = []
        idx = 1

        for key, value in fields.items():
            if key == "description" and isinstance(value, dict):
                set_parts.append(f"{key} = ${idx}::jsonb")
                values.append(json.dumps(value))
            else:
                set_parts.append(f"{key} = ${idx}")
                values.append(value)
            idx += 1

        set_parts.append("updated_at = NOW()")
        set_clause = ", ".join(set_parts)

        values.append(host_id)
        values.append(user_id)

        query = f"""
            UPDATE hosts SET {set_clause}
            WHERE id = ${idx} AND user_id = ${idx + 1}
            RETURNING *
        """

        async with self.pool.acquire(timeout=10) as conn:
            row = await conn.fetchrow(query, *values)

        return dict(row) if row else None

    async def delete(self, host_id: str, user_id: str) -> bool:
        """Delete a host. Returns True if a row was deleted."""
        async with self.pool.acquire(timeout=10) as conn:
            result = await conn.execute(
                "DELETE FROM hosts WHERE id = $1 AND user_id = $2",
                host_id,
                user_id,
            )
        return result == "DELETE 1"

    async def update_avatar(
        self,
        host_id: str,
        *,
        avatar_url: str | None,
        avatar_status: str,
        avatar_generation_id: str | None = None,
    ) -> None:
        """Update avatar fields (no user_id check -- called from ARQ worker)."""
        async with self.pool.acquire(timeout=10) as conn:
            await conn.execute(
                """
                UPDATE hosts
                SET avatar_url = $1, avatar_status = $2, avatar_generation_id = $3,
                    updated_at = NOW()
                WHERE id = $4
                """,
                avatar_url,
                avatar_status,
                avatar_generation_id,
                host_id,
            )

    async def delete_schedule_blocks(self, host_id: str) -> None:
        """Delete all schedule blocks assigned to a host."""
        async with self.pool.acquire(timeout=10) as conn:
            await conn.execute(
                "DELETE FROM schedule_blocks WHERE host_id = $1",
                host_id,
            )
