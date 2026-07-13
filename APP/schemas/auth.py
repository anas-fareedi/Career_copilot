"""
Auth-related Pydantic schemas.

SignupRequest / LoginRequest  — request bodies for the auth endpoints.
AuthResponse                  — returned on successful signup/login.
CurrentUserSchema / UserRead  — identity representations.
"""

from pydantic import BaseModel, EmailStr


# ─── Request bodies ───────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    """Body for POST /api/v1/auth/signup."""
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    """Body for POST /api/v1/auth/login."""
    email: EmailStr
    password: str


# ─── Response bodies ──────────────────────────────────────────────────────────

class SessionInfo(BaseModel):
    """Supabase session tokens returned after login/signup."""
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None


class AuthResponse(BaseModel):
    """
    Returned on successful signup or login.

    The client should store `session.access_token` and send it as:
        Authorization: Bearer <access_token>
    on all subsequent requests to protected endpoints.
    """
    user_id: str
    email: str
    session: SessionInfo


class UserRead(BaseModel):
    """Local DB user record returned by GET /auth/me."""
    id: str
    email: str
    name: str | None = None

    model_config = {"from_attributes": True}
