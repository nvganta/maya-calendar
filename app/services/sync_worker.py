"""
Sync background worker — processes the push queue and periodically pulls from Google.

Two tasks run concurrently:
1. Queue processor (every 60s): picks pending SyncQueueItems, pushes/deletes to Google
2. Pull scheduler (every 5 min): pulls changed events from Google for all connected users
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_

from app.core.config import get_settings
from app.core.database import get_session
from app.models.user import User
from app.models.event import Event
from app.models.google_oauth_token import GoogleOAuthToken
from app.models.sync_queue_item import SyncQueueItem
from app.services import google_auth, google_sync

logger = logging.getLogger(__name__)

_QUEUE_INTERVAL_SECONDS = 60
_PULL_INTERVAL_SECONDS = 300  # 5 minutes
_MAX_RETRIES = 3


async def run_sync_worker() -> None:
    """Long-running task. Call from FastAPI lifespan."""
    settings = get_settings()
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        logger.info("Google sync not configured — sync worker disabled.")
        return

    logger.info("Sync worker started.")
    await _reset_stuck_processing_items()
    await asyncio.gather(
        _run_queue_processor(),
        _run_pull_scheduler(),
    )


async def _reset_stuck_processing_items() -> None:
    """On startup, reset items that were left in 'processing' by a previous crash."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    async with get_session() as db:
        result = await db.execute(
            select(SyncQueueItem).where(
                and_(
                    SyncQueueItem.status == "processing",
                    SyncQueueItem.updated_at < cutoff,
                )
            )
        )
        stuck = result.scalars().all()
        for item in stuck:
            item.status = "pending"
        if stuck:
            await db.commit()
            logger.info(f"Reset {len(stuck)} stuck 'processing' items to 'pending'.")


# ---------------------------------------------------------------------------
# Queue processor — push local changes to Google
# ---------------------------------------------------------------------------

async def _run_queue_processor() -> None:
    while True:
        try:
            await _process_pending_queue()
        except Exception as e:
            logger.error(f"Sync queue processor error: {e}", exc_info=True)
        await asyncio.sleep(_QUEUE_INTERVAL_SECONDS)


async def _process_pending_queue() -> None:
    async with get_session() as db:
        result = await db.execute(
            select(SyncQueueItem).where(
                and_(
                    SyncQueueItem.status == "pending",
                    SyncQueueItem.external_provider == "google",
                    SyncQueueItem.retry_count < _MAX_RETRIES,
                )
            ).order_by(SyncQueueItem.created_at).limit(50)
        )
        items = result.scalars().all()

        if not items:
            return

        logger.info(f"Processing {len(items)} sync queue item(s).")

        for item in items:
            item.status = "processing"
        await db.commit()

        for item in items:
            try:
                await _process_single_item(item, db)
            except Exception as e:
                logger.error(f"Failed to process sync item {item.id}: {e}")
                item.status = "failed"
                item.error_message = str(e)[:500]
                item.retry_count += 1
                if item.retry_count < _MAX_RETRIES:
                    item.status = "pending"  # retry later

            await db.commit()


async def _process_single_item(item: SyncQueueItem, db) -> None:
    """Process a single sync queue item."""
    # Get user and credentials
    user_result = await db.execute(select(User).where(User.id == item.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        item.status = "failed"
        item.error_message = "User not found"
        return

    creds = await google_auth.get_valid_credentials(user, db)
    if not creds:
        item.status = "failed"
        item.error_message = "No valid Google credentials"
        return

    if item.action == "create" or item.action == "update":
        if not item.event_id:
            item.status = "failed"
            item.error_message = "No event_id for create/update"
            return
        event_result = await db.execute(select(Event).where(Event.id == item.event_id))
        event = event_result.scalar_one_or_none()
        if not event:
            item.status = "failed"
            item.error_message = "Event not found (may have been deleted)"
            return
        google_id = await google_sync.push_event_to_google(user, event, creds, db)
        if google_id:
            item.status = "completed"
        else:
            raise Exception("push_event_to_google returned None")

    elif item.action == "delete":
        if not item.external_event_id:
            item.status = "failed"
            item.error_message = "No external_event_id for delete"
            return
        success = await google_sync.delete_from_google(item.external_event_id, creds)
        if success:
            item.status = "completed"
        else:
            raise Exception("delete_from_google returned False")

    else:
        item.status = "failed"
        item.error_message = f"Unknown action: {item.action}"


# ---------------------------------------------------------------------------
# Pull scheduler — fetch changes from Google
# ---------------------------------------------------------------------------

async def _run_pull_scheduler() -> None:
    # Wait a bit on startup to let things settle
    await asyncio.sleep(30)
    while True:
        try:
            await _pull_all_connected_users()
        except Exception as e:
            logger.error(f"Pull scheduler error: {e}", exc_info=True)
        await asyncio.sleep(_PULL_INTERVAL_SECONDS)


async def _pull_all_connected_users() -> None:
    async with get_session() as db:
        # Find all users with Google tokens
        result = await db.execute(
            select(User, GoogleOAuthToken)
            .join(GoogleOAuthToken, GoogleOAuthToken.user_id == User.id)
        )
        rows = result.all()

        if not rows:
            return

        logger.info(f"Pulling Google Calendar changes for {len(rows)} user(s).")

        for user, token in rows:
            try:
                creds = await google_auth.get_valid_credentials(user, db)
                if not creds:
                    continue

                # Get sync preferences from user.preferences
                prefs = user.preferences or {}
                sync_token = prefs.get("google_sync_token")
                calendar_id = prefs.get("google_calendar_id", "primary")

                sync_result, new_token = await google_sync.pull_from_google(
                    user, creds, db, calendar_id=calendar_id, sync_token=sync_token,
                )

                # Store new sync token in user preferences
                if new_token and new_token != sync_token:
                    prefs = (user.preferences or {}).copy()
                    prefs["google_sync_token"] = new_token
                    user.preferences = prefs
                    await db.commit()

                if sync_result.pulled or sync_result.deleted:
                    logger.info(f"User {user.id}: pulled {sync_result.pulled}, deleted {sync_result.deleted}")

            except Exception as e:
                logger.error(f"Pull sync failed for user {user.id}: {e}")
                try:
                    await db.rollback()
                except Exception:
                    pass
