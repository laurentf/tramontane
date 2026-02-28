"""Avatar generation service -- ARQ background task for Leonardo AI."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.core.config import Settings, get_settings
from app.features.hosts.repositories.host_repository import HostRepository
from app.features.hosts.templates import get_template
from app.providers.image.leonardo.adapter import LeonardoAdapter
from app.providers.storage.supabase.storage import SupabaseStorageService

logger = structlog.get_logger(__name__)

_IMAGE_DOWNLOAD_TIMEOUT = 30.0


async def generate_host_avatar(ctx: dict[str, Any], host_id: str) -> None:
    """ARQ task: generate an avatar for a host via Leonardo AI.

    Fetches the host's avatar_prompt, submits generation, polls for
    completion, and updates the host record with the result.
    """
    pool = ctx["pool"]
    settings = get_settings()
    repo = HostRepository(pool)

    try:
        # Check if Leonardo is configured.
        if settings.leonardo_api_key is None:
            logger.info("leonardo_not_configured", host_id=host_id, action="skip")
            await repo.update_avatar(
                host_id,
                avatar_url=None,
                avatar_status="skipped",
            )
            return

        host = await repo.get_by_id_unscoped(host_id)
        if host is None:
            logger.warning("avatar_host_not_found", host_id=host_id)
            return

        avatar_prompt = host.get("avatar_prompt")
        if not avatar_prompt:
            logger.warning("avatar_no_prompt", host_id=host_id)
            await repo.update_avatar(
                host_id,
                avatar_url=None,
                avatar_status="failed",
            )
            return

        adapter = LeonardoAdapter(
            api_key=settings.leonardo_api_key.get_secret_value(),
        )

        # Resolve generation params from template.
        leo_params: dict = {}
        template = get_template(host.get("template_id", ""))
        if template:
            leo_params = template.avatar_generation_params.get("leonardo", {})

        # Submit generation.
        generation_id = await adapter.generate_avatar(
            avatar_prompt,
            model_id=leo_params.get("model_id"),
            preset_style=leo_params.get("preset_style"),
            alchemy=leo_params.get("alchemy"),
            guidance_scale=leo_params.get("guidance_scale"),
        )

        await repo.update_avatar(
            host_id,
            avatar_url=None,
            avatar_status="generating",
            avatar_generation_id=generation_id,
        )

        # Poll for completion.
        image_url = await adapter.poll_generation(generation_id)

        if image_url:
            # Download image from Leonardo CDN and upload to Supabase storage.
            storage_path = await _download_and_store(host_id, image_url, settings)

            if storage_path:
                await repo.update_avatar(
                    host_id,
                    avatar_url=storage_path,
                    avatar_status="complete",
                    avatar_generation_id=generation_id,
                )
                logger.info("avatar_stored", host_id=host_id, path=storage_path)
            else:
                # Storage failed — fall back to CDN URL.
                await repo.update_avatar(
                    host_id,
                    avatar_url=image_url,
                    avatar_status="complete",
                    avatar_generation_id=generation_id,
                )
                logger.warning("avatar_storage_fallback", host_id=host_id, url=image_url)
        else:
            await repo.update_avatar(
                host_id,
                avatar_url=None,
                avatar_status="failed",
                avatar_generation_id=generation_id,
            )
            logger.warning("avatar_generation_failed", host_id=host_id)

    except Exception as exc:
        logger.error("avatar_generation_error", host_id=host_id, error=str(exc))
        try:
            await repo.update_avatar(
                host_id,
                avatar_url=None,
                avatar_status="failed",
            )
        except Exception:
            logger.error("avatar_status_update_failed", host_id=host_id)


async def _download_and_store(
    host_id: str,
    image_url: str,
    settings: Settings,
) -> str | None:
    """Download image from URL and upload to Supabase private storage."""
    try:
        async with httpx.AsyncClient(timeout=_IMAGE_DOWNLOAD_TIMEOUT) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()

        storage = SupabaseStorageService(
            supabase_url=settings.supabase_url,
            supabase_secret_key=settings.supabase_secret_key.get_secret_value(),
        )
        return await storage.upload_avatar(host_id, resp.content)
    except Exception:
        logger.exception("avatar_download_store_failed", host_id=host_id, url=image_url)
        return None


async def enqueue_avatar_generation(redis_pool: Any, host_id: str) -> None:
    """Enqueue an avatar generation job via ARQ."""
    await redis_pool.enqueue_job("generate_host_avatar", host_id)
    logger.info("avatar_job_enqueued", host_id=host_id)
