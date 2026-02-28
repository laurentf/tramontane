"""JWT verification and authorization dependencies."""

import logging
import time
from functools import lru_cache

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, ForbiddenError, ServiceUnavailableError

logger = logging.getLogger(__name__)

__all__ = [
    "get_current_user_id",
    "get_optional_user_id",
    "get_ws_user_id",
    "require_admin",
]

# Admin check cache: user_id -> (is_admin, timestamp)
_admin_cache: dict[str, tuple[bool, float]] = {}
_ADMIN_CACHE_TTL = 300  # 5 minutes

security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=4)
def _get_jwks_client(supabase_url: str) -> PyJWKClient:
    """Get cached JWKS client for Supabase project."""
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=300)


def _verify_token(token: str, settings: Settings) -> dict:
    """Verify JWT and return decoded payload."""
    jwks_client = _get_jwks_client(settings.supabase_url)
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=[signing_key.algorithm_name],
        audience="authenticated",
        options={"verify_aud": True},
    )


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> str:
    """Verify JWT and extract user ID."""
    if credentials is None:
        raise AuthenticationError("Bearer authentication required")

    try:
        payload = _verify_token(credentials.credentials, settings)
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Token missing subject claim")
        return user_id
    except jwt.exceptions.PyJWTError as e:
        logger.warning("JWT verification failed: %s", e)
        raise AuthenticationError("Invalid or expired token") from e


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> str | None:
    """Verify JWT and extract user ID, or return None if no credentials."""
    if credentials is None:
        return None

    try:
        payload = _verify_token(credentials.credentials, settings)
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Token missing subject claim")
        return user_id
    except jwt.exceptions.PyJWTError as e:
        logger.warning("JWT verification failed: %s", e)
        raise AuthenticationError("Invalid or expired token") from e


def get_ws_user_id(token: str, settings: Settings) -> str:
    """Verify JWT from a WebSocket query parameter."""
    if not token:
        raise AuthenticationError("Token required")
    try:
        payload = _verify_token(token, settings)
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Token missing subject claim")
        return user_id
    except jwt.exceptions.PyJWTError as e:
        logger.warning("WebSocket JWT verification failed: %s", e)
        raise AuthenticationError("Invalid or expired token") from e


def is_admin(user_email: str, settings: Settings) -> bool:
    """Check if user email is in admin list."""
    return user_email.lower() in [email.lower() for email in settings.admin_emails]


async def require_admin(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings),
) -> str:
    """Verify user is admin."""
    now = time.monotonic()
    cached = _admin_cache.get(user_id)
    if cached and (now - cached[1]) < _ADMIN_CACHE_TTL:
        if not cached[0]:
            raise ForbiddenError()
        return user_id

    if not hasattr(request.app.state, "pool") or request.app.state.pool is None:
        raise ServiceUnavailableError("Database not available")

    pool = request.app.state.pool

    async with pool.acquire(timeout=10) as conn:
        email = await conn.fetchval(
            "SELECT email FROM auth.users WHERE id = $1",
            user_id,
        )

    if email is None:
        _admin_cache[user_id] = (False, now)
        raise ForbiddenError()

    admin = is_admin(email, settings)
    _admin_cache[user_id] = (admin, now)

    if not admin:
        raise ForbiddenError()

    return user_id
