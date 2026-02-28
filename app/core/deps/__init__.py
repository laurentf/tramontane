"""FastAPI dependency injection providers."""

from app.core.deps.db import get_db_connection, get_db_pool, get_supabase_client
from app.core.deps.hosts import get_host_deps
from app.core.deps.storage import get_storage_service

__all__ = [
    "get_db_connection",
    "get_db_pool",
    "get_host_deps",
    "get_storage_service",
    "get_supabase_client",
]
