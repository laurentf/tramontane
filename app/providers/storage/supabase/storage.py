"""Supabase Storage service for avatar/media management using async client."""

import logging

from storage3.utils import StorageException

from supabase import AsyncClient, acreate_client

logger = logging.getLogger(__name__)

BUCKET = "pictures"


class SupabaseStorageService:
    """Manages files in Supabase Storage (private bucket) using native async."""

    def __init__(self, supabase_url: str, supabase_secret_key: str) -> None:
        self._url = supabase_url
        self._key = supabase_secret_key
        self._client: AsyncClient | None = None

    async def _get_client(self) -> AsyncClient:
        """Lazily create async Supabase client on first use."""
        if self._client is None:
            self._client = await acreate_client(self._url, self._key)
            logger.info("Supabase async storage client created")
        return self._client

    async def upload_avatar(self, host_id: str, image_bytes: bytes) -> str:
        path = f"avatars/{host_id}/avatar.png"
        try:
            client = await self._get_client()
            await client.storage.from_(BUCKET).upload(
                path,
                image_bytes,
                {"content-type": "image/png", "upsert": "true"},
            )
            logger.info("Avatar uploaded for host %s", host_id)
            return path
        except StorageException as e:
            logger.error("Failed to upload avatar for host %s: %s", host_id, e)
            raise

    async def delete_avatar(self, path: str) -> None:
        try:
            client = await self._get_client()
            await client.storage.from_(BUCKET).remove([path])
            logger.info("Deleted avatar at %s", path)
        except StorageException as e:
            logger.warning("Failed to delete avatar at %s (non-fatal): %s", path, e)

    async def download_avatar(self, path: str) -> bytes:
        try:
            client = await self._get_client()
            data = await client.storage.from_(BUCKET).download(path)
            return data
        except StorageException:
            logger.exception("Failed to download avatar at path %s", path)
            raise

    async def get_signed_url(self, path: str, expires_in: int = 86400) -> str | None:
        try:
            client = await self._get_client()
            result = await client.storage.from_(BUCKET).create_signed_url(
                path, expires_in
            )
            return result.get("signedURL")
        except StorageException:
            logger.warning("Failed to generate signed URL for %s", path, exc_info=True)
            return None
