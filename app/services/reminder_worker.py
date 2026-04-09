"""
Reminder background worker — checks for due reminders every 60 seconds and fires them.

Currently: marks reminders as sent and logs them.
Future: POST to Maya's notification API to push the reminder to the user's chat.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, and_

from app.core.config import get_settings
from app.core.database import get_session
from app.models.reminder import Reminder
from app.models.user import User

logger = logging.getLogger(__name__)

_CHECK_INTERVAL_SECONDS = 60


async def run_reminder_worker() -> None:
    """Long-running task. Call from FastAPI lifespan."""
    logger.info("Reminder worker started.")
    while True:
        try:
            await _process_due_reminders()
        except Exception as e:
            logger.error(f"Reminder worker error: {e}", exc_info=True)
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)


async def _process_due_reminders() -> None:
    now = datetime.now(timezone.utc)

    async with get_session() as db:
        result = await db.execute(
            select(Reminder, User)
            .join(User, Reminder.user_id == User.id)
            .where(
                and_(
                    Reminder.is_sent == False,  # noqa: E712
                    Reminder.remind_at <= now,
                )
            )
            .order_by(Reminder.remind_at)
        )
        rows = result.all()

        if not rows:
            return

        settings = get_settings()
        logger.info(f"Firing {len(rows)} due reminder(s).")

        for reminder, user in rows:
            try:
                delivered = await _deliver_reminder(reminder, user, settings)
                if delivered:
                    reminder.is_sent = True
                    await db.commit()
            except Exception as e:
                logger.error(f"Failed to process reminder {reminder.id}: {e}")
                await db.rollback()


async def _deliver_reminder(reminder: Reminder, user: User, settings) -> bool:
    """
    Deliver a reminder. Attempts to push via Maya's API if credentials are set.
    Falls back to logging if Maya credentials aren't configured yet.
    Returns True if delivery succeeded (or no push was attempted), False on failure.
    """
    logger.info(
        f"REMINDER [{user.email}]: {reminder.message} "
        f"(due {reminder.remind_at.isoformat()}, maya_user_id={user.maya_user_id})"
    )

    # Push via Maya when credentials are available
    if settings.MAYA_CLIENT_ID and settings.MAYA_CLIENT_SECRET:
        try:
            await _push_to_maya(reminder, user, settings)
        except Exception as e:
            logger.warning(f"Could not push reminder to Maya: {e}")
            return False

    return True


async def _push_to_maya(reminder: Reminder, user: User, settings) -> None:
    """
    POST the reminder as a proactive message to Maya's notification endpoint.
    Maya will forward it to the user's chat session.
    """
    import hashlib
    import hmac
    import json
    import time

    timestamp = str(int(time.time()))
    # Serialize once — same bytes used for both HMAC and request body.
    body = json.dumps({"maya_user_id": user.maya_user_id, "message": reminder.message}, separators=(",", ":"))
    message = f"{timestamp}.{body}"
    signature = hmac.new(
        settings.MAYA_CLIENT_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.MAYA_API_URL}/api/agents/notify",
            content=body.encode(),
            headers={
                "Content-Type": "application/json",
                "X-Maya-Client-ID": settings.MAYA_CLIENT_ID,
                "X-Maya-Signature": signature,
                "X-Maya-Timestamp": timestamp,
            },
        )
        resp.raise_for_status()
