"""Storage provider dependency — cached singleton."""

from functools import cache

from app.core.config import get_settings
from app.providers.storage import StorageProvider
from app.providers.storage.supabase.storage import SupabaseStorageService


@cache
def _get_storage_service() -> StorageProvider:
    settings = get_settings()
    return SupabaseStorageService(
        supabase_url=settings.supabase_url,
        supabase_secret_key=settings.supabase_secret_key.get_secret_value(),
    )


def get_storage_service() -> StorageProvider:
    """Get the storage provider singleton."""
    return _get_storage_service()
