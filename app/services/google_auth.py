"""
Google OAuth 2.0 service — handles the authorization flow for Google Calendar access.

Flow:
1. get_auth_url() → returns URL to Google consent screen
2. handle_callback(code) → exchanges code for tokens, stores encrypted in DB
3. get_valid_credentials(user) → returns fresh credentials, auto-refreshing if expired
4. disconnect(user) → revokes token and removes from DB
"""

import logging
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.google_oauth_token import GoogleOAuthToken
from app.models.user import User

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _build_flow() -> Flow:
    """Build a Google OAuth flow from app settings."""
    settings = get_settings()
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    return flow


def get_auth_url(state: str | None = None) -> str:
    """Generate the Google OAuth consent screen URL.

    Args:
        state: Opaque string passed through the OAuth flow (e.g. user ID).
    """
    flow = _build_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",  # request refresh_token
        include_granted_scopes="true",
        prompt="consent",  # always show consent to get refresh_token
        state=state,
    )
    return auth_url


async def handle_callback(
    code: str, user: User, db: AsyncSession
) -> GoogleOAuthToken:
    """Exchange the authorization code for tokens and store them.

    The EncryptedText TypeDecorator on GoogleOAuthToken automatically
    encrypts tokens before they hit the database.
    """
    flow = _build_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Check for existing token (reconnecting)
    result = await db.execute(
        select(GoogleOAuthToken).where(GoogleOAuthToken.user_id == user.id)
    )
    token_row = result.scalar_one_or_none()

    if token_row:
        token_row.access_token = creds.token
        token_row.refresh_token = creds.refresh_token or token_row.refresh_token
        token_row.token_expires_at = creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else None
        token_row.scopes = " ".join(creds.scopes or SCOPES)
    else:
        token_row = GoogleOAuthToken(
            user_id=user.id,
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            token_expires_at=creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else None,
            google_email=None,  # populated on first sync
            scopes=" ".join(creds.scopes or SCOPES),
        )
        db.add(token_row)

    await db.commit()
    await db.refresh(token_row)
    logger.info(f"Google OAuth tokens stored for user {user.id}")
    return token_row


async def get_valid_credentials(user: User, db: AsyncSession) -> Credentials | None:
    """Get valid Google credentials for a user, refreshing if expired.

    Returns None if the user hasn't connected Google.
    """
    result = await db.execute(
        select(GoogleOAuthToken).where(GoogleOAuthToken.user_id == user.id)
    )
    token_row = result.scalar_one_or_none()
    if not token_row:
        return None

    settings = get_settings()
    creds = Credentials(
        token=token_row.access_token,
        refresh_token=token_row.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=token_row.scopes.split() if token_row.scopes else SCOPES,
    )

    # Check if expired and refresh
    if token_row.token_expires_at and token_row.token_expires_at <= datetime.now(timezone.utc):
        if not creds.refresh_token:
            logger.warning(f"Google token expired and no refresh token for user {user.id}")
            return None
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            # Update stored tokens
            token_row.access_token = creds.token
            token_row.token_expires_at = creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else None
            await db.commit()
            logger.info(f"Refreshed Google token for user {user.id}")
        except Exception as e:
            logger.error(f"Failed to refresh Google token for user {user.id}: {e}")
            return None

    return creds


async def disconnect(user: User, db: AsyncSession) -> bool:
    """Revoke Google token and remove from database.

    Returns True if disconnected, False if wasn't connected.
    """
    result = await db.execute(
        select(GoogleOAuthToken).where(GoogleOAuthToken.user_id == user.id)
    )
    token_row = result.scalar_one_or_none()
    if not token_row:
        return False

    # Attempt to revoke the token with Google
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token_row.access_token},
            )
    except Exception as e:
        logger.warning(f"Failed to revoke Google token (continuing with local cleanup): {e}")

    await db.delete(token_row)
    await db.commit()
    logger.info(f"Google account disconnected for user {user.id}")
    return True


async def get_connection_status(user: User, db: AsyncSession) -> dict:
    """Get the current Google connection status for a user."""
    result = await db.execute(
        select(GoogleOAuthToken).where(GoogleOAuthToken.user_id == user.id)
    )
    token_row = result.scalar_one_or_none()
    if not token_row:
        return {"connected": False}

    return {
        "connected": True,
        "google_email": token_row.google_email,
        "scopes": token_row.scopes,
        "token_expires_at": token_row.token_expires_at.isoformat() if token_row.token_expires_at else None,
        "connected_at": token_row.created_at.isoformat(),
    }
