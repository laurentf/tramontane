"""Database and Supabase client dependencies."""

from collections.abc import AsyncGenerator

import asyncpg
from fastapi import Depends, Request

from app.core.exceptions import ServiceUnavailableError
from supabase import AsyncClient


async def get_db_pool(request: Request) -> asyncpg.Pool:
    """Get database connection pool from app state."""
    if not hasattr(request.app.state, "pool") or request.app.state.pool is None:
        raise ServiceUnavailableError("Database not available")
    return request.app.state.pool


async def get_db_connection(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> AsyncGenerator[asyncpg.Connection, None]:
    """Get database connection from pool."""
    async with pool.acquire(timeout=10) as conn:
        yield conn


async def get_supabase_client(request: Request) -> AsyncClient:
    """Get cached Supabase client from app state."""
    if not hasattr(request.app.state, "supabase_client"):
        raise ServiceUnavailableError("Supabase client not available")
    return request.app.state.supabase_client
