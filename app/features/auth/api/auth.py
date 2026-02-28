"""Authentication API endpoints."""

import logging

from fastapi import APIRouter, Depends, Request, status
from supabase_auth.errors import (
    AuthApiError,
    AuthInvalidCredentialsError,
    AuthWeakPasswordError,
)

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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_auth_service(
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
        logger.error("Signup failed: %s (status=%s, code=%s)", e.message, e.status, e.code)
        raise AppError("Signup failed") from e
    except Exception as e:
        logger.error("Signup failed: %s", e)
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
        logger.error("Login failed: %s (status=%s)", e.message, e.status)
        raise AppError("Login failed") from e
    except Exception as e:
        logger.error("Login failed: %s", e)
        raise AppError("Login failed") from e


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """Sign out the current user."""
    try:
        auth_header = request.headers.get("authorization", "")
        token = auth_header.removeprefix("Bearer ")
        await auth_service.sign_out(token)
    except Exception as e:
        logger.error("Logout failed for user %s: %s", user_id, e)
        raise AppError("Logout failed") from e


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
    try:
        url = await auth_service.get_google_oauth_url(redirect_url)
        return {"url": url}
    except Exception as e:
        logger.error("Failed to get Google OAuth URL: %s", e)
        raise AppError("Failed to get OAuth URL") from e
