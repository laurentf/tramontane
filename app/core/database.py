"""Database connection pool factory and asyncpg utilities."""

import asyncio
import json

import asyncpg
import structlog
from asyncpg import InterfaceError

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Module-level singleton pool for non-FastAPI processes (workers)
_pool: asyncpg.Pool | None = None
_pool_lock: asyncio.Lock | None = None


def _get_pool_lock() -> asyncio.Lock:
    """Get or create the async pool lock (must be called from event loop context)."""
    global _pool_lock
    if _pool_lock is None:
        _pool_lock = asyncio.Lock()
    return _pool_lock


async def create_pool(
    min_size: int | None = None,
    max_size: int | None = None,
) -> asyncpg.Pool:
    """Create an asyncpg connection pool with standard settings."""
    settings = get_settings()
    return await asyncpg.create_pool(
        dsn=settings.database_url.get_secret_value(),
        min_size=min_size if min_size is not None else settings.db_pool_min_size,
        max_size=max_size if max_size is not None else settings.db_pool_max_size,
        command_timeout=settings.db_pool_command_timeout,
        max_inactive_connection_lifetime=settings.db_pool_max_inactive_lifetime,
        statement_cache_size=0,  # Required for Supabase/pgbouncer
    )


async def get_pool(
    min_size: int | None = None, max_size: int | None = None
) -> asyncpg.Pool:
    """Get or create a persistent database pool for non-FastAPI processes."""
    global _pool
    if is_pool_closed(_pool):
        async with _get_pool_lock():
            if is_pool_closed(_pool):
                _pool = await create_pool(min_size=min_size, max_size=max_size)
                logger.info("Created persistent database pool for process")
    return _pool  # type: ignore[return-value]


def parse_jsonb(val: str | dict | list | None) -> dict | list | None:
    """Parse a JSONB value from asyncpg (string → parsed, already-parsed → passthrough)."""
    if val is None:
        return None
    if isinstance(val, str):
        return json.loads(val)
    return val


def is_pool_closed(pool: asyncpg.Pool | None) -> bool:
    """Check if a pool is closed or None."""
    if pool is None:
        return True
    try:
        _ = pool.get_size()
    except InterfaceError:
        return True
    else:
        return False
