"""
Google Calendar OAuth endpoints.

GET  /api/google/auth-url     → Generate consent screen URL
GET  /api/google/callback     → OAuth redirect handler (exchanges code for tokens)
POST /api/google/disconnect   → Revoke token and disconnect
GET  /api/google/status       → Check connection status
"""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.services import google_auth

logger = logging.getLogger(__name__)

router = APIRouter()


def _google_configured() -> bool:
    """Check if Google OAuth credentials are configured."""
    settings = get_settings()
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


async def _get_user_by_id(user_id: str, db: AsyncSession) -> User:
    """Look up a user by UUID string. Raises 404 if not found."""
    try:
        parsed_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    result = await db.execute(select(User).where(User.id == parsed_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/auth-url")
async def google_auth_url(user_id: str = Query(..., description="Internal user UUID")):
    """Generate the Google OAuth consent screen URL.

    The user_id is embedded in a signed state token (with nonce + timestamp)
    to prevent CSRF attacks on the callback.
    """
    if not _google_configured():
        raise HTTPException(status_code=503, detail="Google Calendar sync is not configured")

    url = google_auth.get_auth_url(user_id=user_id)
    return {"auth_url": url}


@router.get("/callback")
async def google_callback(
    code: str | None = Query(default=None),
    state: str = Query(...),
    error: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """OAuth callback — Google redirects here after user grants (or denies) access.

    The 'state' parameter is a signed token containing the user ID.
    """
    # Handle user-denied or other Google errors
    if error:
        raise HTTPException(status_code=400, detail=f"Google authorization denied: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Verify signed state token (CSRF protection)
    user_id = google_auth._verify_state(state)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired authorization state")

    user = await _get_user_by_id(user_id, db)

    try:
        token_row = await google_auth.handle_callback(code, user, db)
    except Exception as e:
        logger.error(f"Google OAuth callback failed for user {user_id}: {e}")
        raise HTTPException(status_code=400, detail="Failed to complete Google authorization. Please try again.")

    return {
        "status": "connected",
        "google_email": token_row.google_email,
        "message": "Google Calendar connected successfully!",
    }


@router.post("/disconnect")
async def google_disconnect(
    user_id: str = Query(..., description="Internal user UUID"),
    db: AsyncSession = Depends(get_db),
):
    """Revoke Google token and disconnect the account."""
    user = await _get_user_by_id(user_id, db)
    disconnected = await google_auth.disconnect(user, db)

    if not disconnected:
        raise HTTPException(status_code=404, detail="Google account not connected")

    return {"status": "disconnected", "message": "Google Calendar disconnected."}


@router.get("/status")
async def google_status(
    user_id: str = Query(..., description="Internal user UUID"),
    db: AsyncSession = Depends(get_db),
):
    """Check if the user has Google Calendar connected."""
    user = await _get_user_by_id(user_id, db)
    return await google_auth.get_connection_status(user, db)
