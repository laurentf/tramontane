"""Storage provider protocol."""

from typing import Protocol


class StorageProvider(Protocol):
    """Interface for file storage providers (Supabase, S3, local, etc.)."""

    async def upload_avatar(self, host_id: str, image_bytes: bytes) -> str: ...

    async def download_avatar(self, path: str) -> bytes: ...

    async def delete_avatar(self, path: str) -> None: ...

    async def get_signed_url(self, path: str, expires_in: int = 86400) -> str | None: ...
