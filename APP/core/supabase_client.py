"""
Supabase client singleton — strictly lazy initialisation.

The client is created ONLY when `get_supabase()` is first called
(i.e. when an auth route actually handles a request).
Nothing happens at module import time, so missing/placeholder env vars
won't cause connection errors on startup.

Usage:
    from APP.core.supabase_client import get_supabase

    supabase = get_supabase()
    result = supabase.auth.sign_in_with_password(...)
"""

import logging

from supabase import Client, create_client

from APP.core.config import settings

logger = logging.getLogger(__name__)

# Internal singleton — never access this directly; use get_supabase()
_client: Client | None = None


def get_supabase() -> Client:
    """
    Return the Supabase client, creating it on the first call.

    Raises:
        HTTPException 503  — if SUPABASE_URL or SUPABASE_SERVICE_KEY are missing.
        HTTPException 503  — if the Supabase project URL is unreachable.
    """
    global _client

    if _client is not None:
        return _client

    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_KEY

    if not url or url == "https://your-project.supabase.co":
        raise RuntimeError(
            "SUPABASE_URL is not configured. "
            "Set it in your .env file (Supabase Dashboard → Settings → API → Project URL)."
        )
    if not key or "your_supabase" in key:
        raise RuntimeError(
            "SUPABASE_SERVICE_KEY is not configured. "
            "Set it in your .env file (Supabase Dashboard → Settings → API → service_role key)."
        )

    try:
        _client = create_client(url, key)
        logger.info("Supabase client initialised for: %s", url)
        return _client
    except Exception as exc:
        # Don't cache a failed client
        _client = None
        raise RuntimeError(f"Failed to create Supabase client: {exc}") from exc


def reset_supabase_client() -> None:
    """Force re-creation of the client on the next call (useful for testing)."""
    global _client
    _client = None
