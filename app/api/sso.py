"""
SSO validation endpoint — validates a Maya SSO token and issues a JWT.

Flow:
1. Frontend sends sso_token (received from Maya redirect)
2. Backend validates token with Maya's POST /api/sso/validate
3. Backend finds/creates local user from Maya's response
4. Backend issues its own JWT for subsequent API calls
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_jwt
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


class SSOValidateRequest(BaseModel):
    sso_token: str


class SSOValidateResponse(BaseModel):
    access_token: str
    user: dict


@router.post("/validate", response_model=SSOValidateResponse)
async def validate_sso(
    request: SSOValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate a Maya SSO token and return a JWT for this agent's API.

    Called by the frontend after receiving ?sso_token= from Maya's redirect.
    """
    settings = get_settings()

    # Validate token with Maya
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.MAYA_API_URL}/api/sso/validate",
                json={
                    "token": request.sso_token,
                    "client_id": settings.MAYA_CLIENT_ID,
                    "client_secret": settings.MAYA_CLIENT_SECRET,
                },
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to reach Maya SSO endpoint: {e}")
        raise HTTPException(status_code=502, detail="Could not reach Maya for SSO validation")

    if response.status_code != 200:
        logger.warning(f"Maya SSO validation failed: {response.status_code} {response.text}")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO token")

    maya_data = response.json()
    raw_id = maya_data.get("user_id")
    maya_user_id = raw_id if raw_id is not None else maya_data.get("maya_user_id")
    email = maya_data.get("email", "")
    name = maya_data.get("name", "")

    if maya_user_id is None:
        raise HTTPException(status_code=401, detail="Invalid SSO response from Maya")

    try:
        maya_user_id_int = int(maya_user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid SSO response from Maya")

    # Find or create local user (handle race condition on concurrent SSO)
    from sqlalchemy.exc import IntegrityError

    result = await db.execute(select(User).where(User.maya_user_id == maya_user_id_int))
    user = result.scalar_one_or_none()

    if not user:
        try:
            user = User(maya_user_id=maya_user_id_int, email=email, name=name)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Created user from SSO: {user.id} (maya_user_id={maya_user_id_int})")
        except IntegrityError:
            await db.rollback()
            result = await db.execute(select(User).where(User.maya_user_id == maya_user_id_int))
            user = result.scalar_one()
    else:
        # Update email/name if changed
        if email and user.email != email:
            user.email = email
        if name and user.name != name:
            user.name = name
        await db.commit()

    # Issue JWT
    access_token = create_jwt(str(user.id), user.email)

    return SSOValidateResponse(
        access_token=access_token,
        user={
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "timezone": user.timezone,
        },
    )
