"""FastAPI dependency injection providers."""

from app.core.deps.db import get_db_connection, get_db_pool, get_supabase_client

__all__ = [
    "get_db_connection",
    "get_db_pool",
    "get_supabase_client",
]
