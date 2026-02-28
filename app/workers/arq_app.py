"""ARQ worker configuration.

Start worker:
    arq app.workers.arq_app.WorkerSettings
"""

import os
from typing import ClassVar

import structlog
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


async def startup(ctx: dict) -> None:
    """Create shared resources for worker process."""
    from app.core.banner import print_service_line
    from app.core.database import create_pool

    ctx["pool"] = await create_pool()
    print_service_line("worker")


async def shutdown(ctx: dict) -> None:
    """Clean up shared resources."""
    pool = ctx.get("pool")
    if pool:
        await pool.close()


async def ping(ctx: dict) -> str:
    """Health check task."""
    return "pong"


class WorkerSettings:
    functions: ClassVar[list] = [ping]
    cron_jobs: ClassVar[list] = []  # Add cron jobs here
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _get_redis_settings()
    queue_name = os.getenv("ARQ_QUEUE", "arq:queue")
    job_timeout = 900
    max_jobs = 10
    retry_jobs = True
