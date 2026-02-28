"""Host feature dependency injection providers."""

from __future__ import annotations

import asyncpg
from fastapi import Request

from app.core.config import Settings, get_settings
from app.core.deps.db import get_db_pool


async def get_host_deps(request: Request) -> tuple[asyncpg.Pool, Settings]:
    """Get database pool and settings for host operations."""
    pool = await get_db_pool(request)
    settings = get_settings()
    return pool, settings
