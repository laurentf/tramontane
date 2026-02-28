"""Radio settings repository — asyncpg queries."""

from __future__ import annotations

import asyncpg


async def get_by_user(user_id: str, pool: asyncpg.Pool) -> dict | None:
    """Fetch radio settings row for a user."""
    return await pool.fetchrow(
        "SELECT station_name, language, location FROM radio_settings WHERE user_id = $1",
        user_id,
    )


async def ensure_defaults(user_id: str, pool: asyncpg.Pool) -> None:
    """Insert default settings row if none exists."""
    await pool.execute(
        "INSERT INTO radio_settings (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING",
        user_id,
    )


async def update(user_id: str, updates: dict, pool: asyncpg.Pool) -> None:
    """Apply partial updates to a user's settings."""
    if not updates:
        return

    set_parts: list[str] = []
    values: list[object] = []
    for i, (key, value) in enumerate(updates.items(), start=2):
        set_parts.append(f"{key} = ${i}")
        values.append(value)

    await pool.execute(
        f"UPDATE radio_settings SET {', '.join(set_parts)} WHERE user_id = $1",
        user_id,
        *values,
    )
