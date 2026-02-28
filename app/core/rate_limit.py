"""Rate limiting configuration using slowapi."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


def get_user_id_or_ip(request: Request) -> str:
    """Rate-limit key: IP address."""
    return get_remote_address(request)


def _get_limiter() -> Limiter:
    """Create rate limiter with lazy settings access."""
    settings = get_settings()
    return Limiter(
        key_func=get_user_id_or_ip,
        storage_uri=settings.redis_url.get_secret_value() if settings.redis_url else "memory://",
    )


limiter = _get_limiter()
