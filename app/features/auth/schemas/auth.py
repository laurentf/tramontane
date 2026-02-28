"""Pydantic schemas for authentication requests and responses."""

from pydantic import BaseModel, EmailStr, Field


class SignUpRequest(BaseModel):
    """Request schema for user signup."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """Request schema for user login."""

    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Response schema for authentication operations."""

    access_token: str
    refresh_token: str
    user_id: str
    email: str
    confirmation_required: bool = False


class SignUpResponse(BaseModel):
    """Response schema for signup — may or may not include tokens."""

    user_id: str
    email: str
    confirmation_required: bool = False
    access_token: str | None = None
    refresh_token: str | None = None


class SessionResponse(BaseModel):
    """Response schema for session information."""

    user_id: str
    email: str
    is_admin: bool = False
    expires_at: int | None = None


class GoogleCallbackRequest(BaseModel):
    """Request schema for Google OAuth callback."""

    code: str
