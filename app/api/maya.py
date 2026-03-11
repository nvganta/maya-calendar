import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import require_maya_signature
from app.models.user import User
from app.schemas.maya import ProvisionRequest, ProvisionResponse, ChatRequest, ChatResponse
from app.services.intent import parse_intent
from app.services.calendar import handle_calendar_action

router = APIRouter()


@router.post("/api/maya/provision", response_model=ProvisionResponse)
async def provision(
    request: ProvisionRequest,
    db: AsyncSession = Depends(get_db),
    _signature: str = Depends(require_maya_signature),
):
    """Called by Maya when a user connects this agent from the marketplace."""
    # Check if user already exists
    result = await db.execute(select(User).where(User.maya_user_id == request.maya_user_id))
    user = result.scalar_one_or_none()

    if user:
        return ProvisionResponse(agent_user_id=str(user.id), needs_setup=False)

    # Create new user
    user = User(
        maya_user_id=request.maya_user_id,
        email=request.email,
        name=request.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return ProvisionResponse(agent_user_id=str(user.id), needs_setup=False)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _signature: str = Depends(require_maya_signature),
):
    """Called by Maya every time a user sends a calendar-related message."""
    user = None

    # Primary lookup: agent_user_id (UUID returned by /provision)
    agent_user_id = request.context.agent_user_id
    if agent_user_id:
        try:
            parsed_id = uuid.UUID(agent_user_id)
            result = await db.execute(select(User).where(User.id == parsed_id))
            user = result.scalar_one_or_none()
        except ValueError:
            pass  # Not a valid UUID — fall through to maya_user_id lookup

    # Fallback: look up or create by maya_user_id
    if not user and request.user:
        result = await db.execute(select(User).where(User.maya_user_id == request.user.maya_user_id))
        user = result.scalar_one_or_none()

        if not user:
            # Auto-provision: Maya called /chat before /provision (or provision failed)
            user = User(
                maya_user_id=request.user.maya_user_id,
                email=request.user.email,
                name=request.user.name,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Step 1: Parse intent from natural language
    intent = await parse_intent(
        message=request.message,
        conversation_history=request.conversation_history,
        user_timezone=user.timezone,
    )

    # Step 2: Execute the calendar action
    response_text = await handle_calendar_action(
        intent=intent,
        user=user,
        db=db,
    )

    return ChatResponse(response=response_text)
