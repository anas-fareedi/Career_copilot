"""
Gmail OAuth router — /api/v1/auth/gmail

Handles the Google OAuth 2.0 flow for Gmail access.

Endpoints:
  GET  /auth/gmail/connect     — Returns the Google OAuth authorization URL
  GET  /auth/gmail/callback    — Handles OAuth callback, stores token in DB
  POST /auth/gmail/disconnect  — Revokes and clears stored Gmail token
  GET  /auth/gmail/status      — Returns Gmail connection status for current user

Setup (Google Cloud Console):
  1. Go to https://console.cloud.google.com/
  2. Create a project → APIs & Services → Enable Gmail API
  3. OAuth consent screen → External → add scopes:
       https://www.googleapis.com/auth/gmail.readonly
  4. Credentials → Create OAuth 2.0 Client ID → Web Application
  5. Authorised redirect URI: http://localhost:8000/api/v1/auth/gmail/callback
  6. Copy Client ID and Client Secret → set in .env as GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from APP.core.config import settings
from APP.core.database import get_db
from APP.core.security import CurrentUser, get_current_user, get_or_create_local_user
from APP.models.user import UserPreferences

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/gmail", tags=["Gmail OAuth"])

# Gmail readonly scope — enough to scan job-related emails
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _get_flow(state: str = ""):
    """Build the google_auth_oauthlib Flow object."""
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="google-auth-oauthlib is not installed. Run: pip install google-auth-oauthlib",
        )

    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are not configured. "
                "Set them in your .env file (Google Cloud Console → Credentials)."
            ),
        )

    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=GMAIL_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )
    if state:
        flow.state = state
    return flow


@router.get("/connect", summary="Get Google OAuth authorization URL")
def gmail_connect(
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Returns the Google OAuth authorization URL.
    The frontend should redirect the user to this URL.
    After the user consents, Google redirects back to /auth/gmail/callback.

    The user_id is encoded in the `state` parameter so the callback
    can identify which user to save the token for.
    """
    flow = _get_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",    # request refresh_token
        include_granted_scopes="true",
        prompt="consent",         # always show consent to get refresh_token
        state=current_user.user_id,  # pass user_id through the OAuth state param
    )

    logger.info("Gmail OAuth URL generated for user %s.", current_user.user_id)
    return {
        "authorization_url": auth_url,
        "state": state,
        "instructions": "Redirect the user to `authorization_url` to begin Gmail authorization.",
    }


@router.get("/callback", summary="Handle Google OAuth callback")
def gmail_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="User ID passed through OAuth state"),
    db: Session = Depends(get_db),
):
    """
    Google redirects here after the user grants (or denies) Gmail access.
    Exchanges the auth code for tokens and saves them to the user's preferences.

    The `state` parameter contains the user_id set in /connect.
    After saving the token, redirects to the frontend or returns a success response.
    """
    user_id = state  # we encoded user_id as the OAuth state

    flow = _get_flow(state=state)
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        logger.error("Gmail OAuth token exchange failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth token exchange failed: {exc}",
        )

    credentials = flow.credentials
    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }

    # Save token to user preferences
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)

    prefs.gmail_token = token_data
    prefs.gmail_connected = True
    db.commit()

    logger.info("Gmail connected successfully for user %s.", user_id)

    # If the frontend is running, redirect back to it; otherwise return JSON
    frontend_url = "http://localhost:3000/settings?gmail=connected"
    return RedirectResponse(url=frontend_url, status_code=302)


@router.post("/disconnect", status_code=status.HTTP_200_OK, summary="Disconnect Gmail account")
def gmail_disconnect(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Revoke the Gmail OAuth token and remove it from the database.
    After disconnecting, Gmail inbox scanning will be skipped during discovery.
    """
    user = get_or_create_local_user(current_user, db)

    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
    if not prefs or not prefs.gmail_token:
        return {"status": "not_connected", "message": "Gmail was not connected."}

    # Attempt to revoke the token with Google
    token = prefs.gmail_token.get("token")
    if token:
        try:
            import httpx
            httpx.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token},
                timeout=5,
            )
        except Exception as exc:
            logger.warning("Failed to revoke Gmail token with Google: %s — clearing locally anyway.", exc)

    prefs.gmail_token = None
    prefs.gmail_connected = False
    db.commit()

    logger.info("Gmail disconnected for user %s.", user.id)
    return {"status": "disconnected", "message": "Gmail access has been revoked and removed."}


@router.get("/status", summary="Gmail connection status")
def gmail_status(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return whether the current user has an active Gmail OAuth token."""
    user = get_or_create_local_user(current_user, db)

    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
    connected = bool(prefs and prefs.gmail_connected and prefs.gmail_token)

    return {
        "gmail_connected": connected,
        "message": "Gmail is connected. Inbox will be scanned during job discovery." if connected
        else "Gmail is not connected. Use GET /auth/gmail/connect to authorize.",
    }
