"""Authentication service wrapping Supabase Auth operations."""

from supabase_auth.errors import AuthApiError

from app.features.auth.schemas.auth import AuthResponse, SessionResponse, SignUpResponse
from supabase import AsyncClient


class AuthService:
    """Service for handling authentication operations via Supabase Auth."""

    def __init__(self, supabase: AsyncClient):
        self.supabase = supabase

    async def sign_up(
        self,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> SignUpResponse:
        """Sign up a new user."""
        user_data = {}
        if display_name:
            user_data["display_name"] = display_name

        response = await self.supabase.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {"data": user_data} if user_data else {},
            }
        )

        if response.session:
            return SignUpResponse(
                user_id=response.user.id,
                email=response.user.email,
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
            )

        return SignUpResponse(
            user_id=response.user.id,
            email=response.user.email,
            confirmation_required=True,
        )

    async def sign_in(self, email: str, password: str) -> AuthResponse:
        """Sign in an existing user."""
        response = await self.supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )

        return AuthResponse(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            user_id=response.user.id,
            email=response.user.email,
        )

    async def sign_out(self, access_token: str) -> None:
        """Sign out a user (invalidate refresh token)."""
        await self.supabase.auth.set_session(access_token, access_token)
        await self.supabase.auth.sign_out()

    async def get_session(self, access_token: str) -> SessionResponse | None:
        """Get session information for a token."""
        try:
            user = await self.supabase.auth.get_user(access_token)
            return SessionResponse(
                user_id=user.user.id,
                email=user.user.email,
                expires_at=None,
            )
        except AuthApiError:
            return None

    async def get_google_oauth_url(self, redirect_url: str) -> str:
        """Get Google OAuth URL for client redirect."""
        response = await self.supabase.auth.sign_in_with_oauth(
            {
                "provider": "google",
                "options": {"redirect_to": redirect_url},
            }
        )
        return response.url
