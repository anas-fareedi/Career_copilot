"""
Security utilities — token validation via Supabase.

How it works:
  1. User calls POST /api/v1/auth/signup or /login.
  2. Backend calls Supabase, which returns an access_token (JWT).
  3. Client stores the access_token and sends it as:
       Authorization: Bearer <access_token>
  4. `get_current_user` calls supabase.auth.get_user(token) to validate.
     This delegates validation to Supabase — no local key needed.
  5. `get_or_create_local_user` upserts a local DB row for FK relationships.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import AuthApiError
from sqlalchemy.orm import Session

from APP.core.database import get_db

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=True)


class CurrentUser:
    """Lightweight identity object from the validated Supabase session."""

    def __init__(self, user_id: str, email: Optional[str] = None):
        self.user_id = user_id   # Supabase UUID
        self.email = email or ""


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> CurrentUser:
    """
    FastAPI dependency — validates the access_token via Supabase and returns
    the caller's identity.

    Usage:
        @router.get("/protected")
        def my_route(user: CurrentUser = Depends(get_current_user)):
            ...
    """
    from APP.core.supabase_client import get_supabase

    token = credentials.credentials

    try:
        supabase = get_supabase()
        response = supabase.auth.get_user(token)
        user = response.user

        if not user or not user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return CurrentUser(user_id=str(user.id), email=user.email)

    except AuthApiError as exc:
        logger.debug("Supabase token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except RuntimeError as exc:
        # Supabase client not configured
        logger.error("Supabase client not configured: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


def get_or_create_local_user(current_user: CurrentUser, db: Session):
    """
    Upsert a local DB user row from the Supabase identity.
    Called by routes that need FK relationships (profile, jobs, applications).
    """
    from APP.models.user import User  # local import to avoid circular deps

    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        user = User(id=current_user.user_id, email=current_user.email)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Created local user record for Supabase UUID %s", current_user.user_id)
    return user
