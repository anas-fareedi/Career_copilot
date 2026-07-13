"""
Auth router — /api/v1/auth

Endpoints:
  POST /signup   — Register a new user via Supabase
  POST /login    — Authenticate and receive access_token
  POST /logout   — Invalidate the current session
  GET  /me       — Return current user info (requires valid token)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AuthApiError
from sqlalchemy.orm import Session

from APP.core.database import get_db
from APP.core.security import CurrentUser, get_current_user, get_or_create_local_user
from APP.schemas.auth import AuthResponse, LoginRequest, SessionInfo, SignupRequest, UserRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


def _get_supabase():
    """Helper — get the Supabase client, raising 503 if not configured or unreachable."""
    import httpx
    from APP.core.supabase_client import get_supabase
    try:
        return get_supabase()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Cannot reach Supabase. "
                "Check that SUPABASE_URL in your .env is your real project URL "
                "(e.g. https://abcxyz.supabase.co), not the placeholder."
            ),
        )


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    """
    Create a new account via Supabase Auth.

    Returns an `access_token` that the client must include in subsequent requests:
        Authorization: Bearer <access_token>

    Supabase may send a confirmation email depending on your project settings.
    """
    supabase = _get_supabase()

    try:
        result = supabase.auth.sign_up(
            {"email": body.email, "password": body.password}
        )
    except AuthApiError as exc:
        logger.warning("Signup failed for %s: %s", body.email, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    user = result.user
    session = result.session

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signup failed — no user returned. Check your Supabase settings.",
        )

    # Upsert local DB row
    from APP.models.user import User
    db_user = db.query(User).filter(User.id == str(user.id)).first()
    if not db_user:
        db.add(User(id=str(user.id), email=user.email or body.email))
        db.commit()
        logger.info("New user registered: %s", user.id)

    return AuthResponse(
        user_id=str(user.id),
        email=user.email or body.email,
        session=SessionInfo(
            access_token=session.access_token if session else "",
            refresh_token=session.refresh_token if session else None,
            expires_in=session.expires_in if session else None,
        ),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login with email and password",
)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with Supabase and receive an `access_token`.

    Use this token in all subsequent requests:
        Authorization: Bearer <access_token>
    """
    supabase = _get_supabase()

    try:
        result = supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except AuthApiError as exc:
        logger.warning("Login failed for %s: %s", body.email, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    user = result.user
    session = result.session

    if not user or not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login failed — no session returned.",
        )

    # Upsert local DB row on login too
    from APP.models.user import User
    db_user = db.query(User).filter(User.id == str(user.id)).first()
    if not db_user:
        db.add(User(id=str(user.id), email=user.email or body.email))
        db.commit()
        logger.info("Auto-created local record for existing Supabase user: %s", user.id)

    logger.info("User logged in: %s", user.id)
    return AuthResponse(
        user_id=str(user.id),
        email=user.email or body.email,
        session=SessionInfo(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=session.expires_in,
        ),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and invalidate the current session",
)
def logout(current_user: CurrentUser = Depends(get_current_user)):
    """
    Invalidate the current Supabase session.
    The client should also discard the stored access_token.
    """
    supabase = _get_supabase()
    try:
        supabase.auth.sign_out()
        logger.info("User %s signed out.", current_user.user_id)
    except AuthApiError as exc:
        logger.warning("Sign-out error (non-fatal): %s", exc)
    return None


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current authenticated user",
)
def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validate the token and return the local user record.
    Also upserts the local user row if it doesn't exist yet.
    """
    user = get_or_create_local_user(current_user, db)
    logger.debug("GET /auth/me — user %s", user.id)
    return user
