"""ARQ worker configuration.

Start worker:
    arq app.workers.arq_app.WorkerSettings
"""

import os
from collections.abc import Callable, Coroutine
from typing import Any, ClassVar

import structlog
from arq import cron
from arq.connections import RedisSettings

logger = structlog.get_logger(__name__)


def _get_redis_settings() -> RedisSettings:
    try:
        from app.core.config import get_settings

        settings = get_settings()
        if settings.redis_url:
            return RedisSettings.from_dsn(settings.redis_url.get_secret_value())
    except Exception:
        logger.debug("redis_settings_from_config_failed")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return RedisSettings.from_dsn(redis_url)


async def startup(ctx: dict[str, Any]) -> None:
    """Create shared resources for worker process."""
    from app.core.banner import print_service_line
    from app.core.database import create_pool

    ctx["pool"] = await create_pool()
    print_service_line("worker")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Clean up shared resources."""
    pool = ctx.get("pool")
    if pool:
        await pool.close()


async def ping(ctx: dict[str, Any]) -> str:
    """Health check task."""
    return "pong"


# ---------------------------------------------------------------------------
# Lazy imports to avoid circular dependencies at module level.
# ---------------------------------------------------------------------------


def _get_avatar_task() -> Callable[..., Coroutine[Any, Any, Any]]:
    from app.features.hosts.services.avatar_service import generate_host_avatar

    return generate_host_avatar


def _get_content_segment_task() -> Callable[..., Coroutine[Any, Any, Any]]:
    from app.features.content.services.schedule_engine import generate_content_segment

    return generate_content_segment


def _get_bumpers_task() -> Callable[..., Coroutine[Any, Any, Any]]:
    from app.features.content.services.bumper_generator import generate_bumpers_task

    return generate_bumpers_task


def _get_embed_tracks_task() -> Callable[..., Coroutine[Any, Any, Any]]:
    from app.features.content.services.embedding_ingest import embed_tracks_task

    return embed_tracks_task


def _get_schedule_tick() -> Callable[..., Coroutine[Any, Any, Any]]:
    from app.features.content.services.schedule_engine import schedule_tick

    return schedule_tick


class WorkerSettings:
    functions: ClassVar[list[Callable[..., Coroutine[Any, Any, Any]]]] = [
        ping,
        _get_avatar_task(),
        _get_content_segment_task(),
        _get_bumpers_task(),
        _get_embed_tracks_task(),
    ]
    cron_jobs: ClassVar[list[Any]] = [
        # Schedule engine heartbeat: fires every 60 seconds.
        # Checks for active blocks and dispatches content generation.
        cron(_get_schedule_tick(), second={0}, unique=True),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _get_redis_settings()
    queue_name = os.getenv("ARQ_QUEUE", "arq:queue")
    job_timeout = 900
    max_jobs = 10
    retry_jobs = True
