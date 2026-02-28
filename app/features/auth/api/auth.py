"""Authentication API endpoints."""

from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Depends, Request, status
from supabase_auth.errors import (
    AuthApiError,
    AuthInvalidCredentialsError,
    AuthWeakPasswordError,
)

from app.core.config import get_settings
from app.core.deps import get_supabase_client
from app.core.exceptions import (
    AppError,
    AuthenticationError,
    ConflictError,
    ValidationError,
)
from app.core.rate_limit import limiter
from app.core.security import get_current_user_id
from app.features.auth.schemas.auth import (
    AuthResponse,
    LoginRequest,
    SessionResponse,
    SignUpRequest,
    SignUpResponse,
)
from app.features.auth.services.auth_service import AuthService
from supabase import AsyncClient

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(
    supabase: AsyncClient = Depends(get_supabase_client),
) -> AuthService:
    """Dependency to get AuthService instance."""
    return AuthService(supabase)


@router.post("/signup", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def signup(
    request: Request,
    body: SignUpRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> SignUpResponse:
    """Sign up a new user."""
    try:
        return await auth_service.sign_up(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
        )
    except AuthWeakPasswordError as e:
        raise ValidationError("Password is too weak") from e
    except AuthInvalidCredentialsError as e:
        raise ValidationError("Invalid signup data") from e
    except AuthApiError as e:
        if e.status == 422 or "already registered" in e.message.lower():
            raise ConflictError("User already exists") from e
        if e.status == 400:
            raise ValidationError(e.message) from e
        logger.error("signup_failed", message=e.message, status=e.status, code=e.code)
        raise AppError("Signup failed") from e


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    """Sign in an existing user."""
    try:
        return await auth_service.sign_in(
            email=body.email,
            password=body.password,
        )
    except AuthInvalidCredentialsError as e:
        raise AuthenticationError("Invalid email or password") from e
    except AuthApiError as e:
        if e.status == 400:
            raise AuthenticationError("Invalid email or password") from e
        logger.error("login_failed", message=e.message, status=e.status)
        raise AppError("Login failed") from e


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """Sign out the current user."""
    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ")
    await auth_service.sign_out(token)


@router.get("/session", response_model=SessionResponse)
async def get_session(
    user_id: str = Depends(get_current_user_id),
) -> SessionResponse:
    """Get current session information."""
    return SessionResponse(
        user_id=user_id,
        email="",
        expires_at=None,
    )


@router.get("/google", response_model=dict[str, str])
@limiter.limit("10/minute")
async def get_google_oauth_url(
    request: Request,
    redirect_url: str,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """Get Google OAuth URL for client redirect."""
    settings = get_settings()
    parsed = urlparse(redirect_url)
    redirect_origin = f"{parsed.scheme}://{parsed.netloc}"
    if redirect_origin not in settings.cors_origins:
        raise ValidationError("Invalid redirect URL")
    url = await auth_service.get_google_oauth_url(redirect_url)
    return {"url": url}
