"""
JWT authentication for frontend sessions.

After SSO validation, the backend issues a JWT containing the user's internal UUID.
All frontend-facing API endpoints use `get_current_user` as a FastAPI dependency
to extract and verify the token from the Authorization header.
"""

import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)


def create_jwt(user_id: str, email: str) -> str:
    """Issue a JWT for a frontend session.

    Args:
        user_id: The calendar agent's internal user UUID (string).
        email: User's email for convenience (not used for auth).
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and verify a JWT. Raises on expiry or invalid signature."""
    settings = get_settings()
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency — extracts JWT from Authorization header and returns the User.

    Usage: user: User = Depends(get_current_user)
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = auth_header[7:]  # strip "Bearer "
    try:
        payload = decode_jwt(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    import uuid
    try:
        parsed_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID in token")

    result = await db.execute(select(User).where(User.id == parsed_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
