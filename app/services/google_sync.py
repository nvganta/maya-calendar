"""
Google Calendar sync service — bidirectional sync between local events and Google Calendar.

Pull: fetch changed events from Google → create/update/delete local events
Push: send local event changes to Google Calendar API

Uses Google Calendar API v3 via google-api-python-client.
All Google API calls are offloaded to threads (sync library on async event loop).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.event import Event
from app.models.external_event_mapping import ExternalEventMapping

logger = logging.getLogger(__name__)

PROVIDER = "google"
DEFAULT_CALENDAR_ID = "primary"


@dataclass
class SyncResult:
    """Summary of a sync operation."""
    pulled: int = 0
    pushed: int = 0
    deleted: int = 0
    errors: list[str] = field(default_factory=list)


def _build_calendar_service(creds: Credentials):
    """Build a Google Calendar API service client."""
    return build("calendar", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Field mapping: Google Calendar event ↔ local Event
# ---------------------------------------------------------------------------

def _google_event_to_local(g_event: dict, user: User) -> dict:
    """Convert a Google Calendar event dict to local Event field dict.

    Returns a dict of fields suitable for Event(**fields) or updating an existing Event.
    """
    # Handle timed events vs all-day events
    start_data = g_event.get("start", {})
    end_data = g_event.get("end", {})

    if "dateTime" in start_data:
        start_time = datetime.fromisoformat(start_data["dateTime"])
        end_time = datetime.fromisoformat(end_data.get("dateTime", start_data["dateTime"]))
        is_all_day = False
    elif "date" in start_data:
        # All-day event: date only (no time component)
        start_time = datetime.strptime(start_data["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_date_str = end_data.get("date", start_data["date"])
        end_time = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        is_all_day = True
    else:
        return {}

    # Ensure timezone-aware
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    # Recurrence: Google uses ["RRULE:FREQ=WEEKLY;BYDAY=MO"], we store "FREQ=WEEKLY;BYDAY=MO"
    recurrence = None
    if g_event.get("recurrence"):
        for rule in g_event["recurrence"]:
            if rule.startswith("RRULE:"):
                recurrence = rule[6:]  # strip "RRULE:" prefix
                break

    return {
        "title": g_event.get("summary", "(No title)"),
        "description": g_event.get("description"),
        "start_time": start_time,
        "end_time": end_time,
        "location": g_event.get("location"),
        "is_all_day": is_all_day,
        "recurrence": recurrence,
    }


def _local_event_to_google(event: Event) -> dict:
    """Convert a local Event to a Google Calendar API event body."""
    tz_name = "UTC"

    if event.is_all_day:
        body = {
            "start": {"date": event.start_time.strftime("%Y-%m-%d")},
            "end": {"date": event.end_time.strftime("%Y-%m-%d")},
        }
    else:
        body = {
            "start": {"dateTime": event.start_time.isoformat(), "timeZone": tz_name},
            "end": {"dateTime": event.end_time.isoformat(), "timeZone": tz_name},
        }

    body["summary"] = event.title
    if event.description:
        body["description"] = event.description
    if event.location:
        body["location"] = event.location

    # Recurrence: we store "FREQ=WEEKLY;BYDAY=MO", Google wants ["RRULE:FREQ=WEEKLY;BYDAY=MO"]
    if event.recurrence:
        body["recurrence"] = [f"RRULE:{event.recurrence}"]

    return body


# ---------------------------------------------------------------------------
# Pull from Google
# ---------------------------------------------------------------------------

async def pull_from_google(
    user: User,
    creds: Credentials,
    db: AsyncSession,
    calendar_id: str = DEFAULT_CALENDAR_ID,
    sync_token: str | None = None,
) -> tuple[SyncResult, str | None]:
    """Pull changed events from Google Calendar into the local database.

    Uses incremental sync via syncToken when available, otherwise does a
    full sync of events from the past 30 days to 1 year ahead.

    Returns (SyncResult, new_sync_token).
    """
    result = SyncResult()
    service = _build_calendar_service(creds)

    # Build list request params
    params = {"calendarId": calendar_id, "singleEvents": False, "maxResults": 250}
    if sync_token:
        params["syncToken"] = sync_token
    else:
        # Full sync: past 30 days to 1 year ahead
        now = datetime.now(timezone.utc)
        params["timeMin"] = (now - timedelta(days=30)).isoformat()
        params["timeMax"] = (now + timedelta(days=365)).isoformat()

    new_sync_token = None
    all_google_events = []

    try:
        # Paginate through results
        while True:
            response = await asyncio.to_thread(
                lambda: service.events().list(**params).execute()
            )
            all_google_events.extend(response.get("items", []))
            next_page = response.get("nextPageToken")
            if next_page:
                params["pageToken"] = next_page
            else:
                new_sync_token = response.get("nextSyncToken")
                break
    except Exception as e:
        error_str = str(e)
        # If syncToken is invalid (e.g. expired), fall back to full sync
        if "410" in error_str and sync_token:
            logger.warning(f"Sync token expired for user {user.id}, falling back to full sync")
            return await pull_from_google(user, creds, db, calendar_id, sync_token=None)
        logger.error(f"Failed to list Google events for user {user.id}: {e}")
        result.errors.append(f"Failed to fetch events: {e}")
        return result, sync_token

    # Process each Google event
    for g_event in all_google_events:
        try:
            google_event_id = g_event["id"]
            status = g_event.get("status", "confirmed")

            # Look up existing mapping
            mapping_result = await db.execute(
                select(ExternalEventMapping).where(and_(
                    ExternalEventMapping.external_provider == PROVIDER,
                    ExternalEventMapping.external_event_id == google_event_id,
                ))
            )
            mapping = mapping_result.scalar_one_or_none()

            if status == "cancelled":
                # Event was deleted in Google — delete locally if we have it
                if mapping:
                    event_result = await db.execute(
                        select(Event).where(Event.id == mapping.internal_event_id)
                    )
                    event = event_result.scalar_one_or_none()
                    if event:
                        await db.delete(event)
                        result.deleted += 1
                    # Mapping cascades on event delete
                continue

            # Convert Google event to local fields
            fields = _google_event_to_local(g_event, user)
            if not fields:
                continue

            if mapping:
                # Update existing local event
                event_result = await db.execute(
                    select(Event).where(Event.id == mapping.internal_event_id)
                )
                event = event_result.scalar_one_or_none()
                if event:
                    for key, value in fields.items():
                        setattr(event, key, value)
                    mapping.last_synced_at = datetime.now(timezone.utc)
                    result.pulled += 1
            else:
                # Create new local event from Google
                event = Event(user_id=user.id, **fields)
                db.add(event)
                await db.flush()  # get event.id before creating mapping
                db.add(ExternalEventMapping(
                    internal_event_id=event.id,
                    external_provider=PROVIDER,
                    external_event_id=google_event_id,
                    external_calendar_id=calendar_id,
                ))
                result.pulled += 1

        except Exception as e:
            logger.warning(f"Failed to process Google event {g_event.get('id', '?')}: {e}")
            result.errors.append(f"Event {g_event.get('summary', '?')}: {e}")

    await db.commit()
    logger.info(f"Pull sync for user {user.id}: {result.pulled} pulled, {result.deleted} deleted, {len(result.errors)} errors")
    return result, new_sync_token


# ---------------------------------------------------------------------------
# Push to Google
# ---------------------------------------------------------------------------

async def push_event_to_google(
    user: User,
    event: Event,
    creds: Credentials,
    db: AsyncSession,
    calendar_id: str = DEFAULT_CALENDAR_ID,
) -> str | None:
    """Create or update an event in Google Calendar.

    Returns the Google event ID on success, None on failure.
    """
    service = _build_calendar_service(creds)
    body = _local_event_to_google(event)

    # Check if this event already has a Google mapping
    mapping_result = await db.execute(
        select(ExternalEventMapping).where(and_(
            ExternalEventMapping.internal_event_id == event.id,
            ExternalEventMapping.external_provider == PROVIDER,
        ))
    )
    mapping = mapping_result.scalar_one_or_none()

    try:
        if mapping:
            # Update existing Google event
            g_event = await asyncio.to_thread(
                lambda: service.events().update(
                    calendarId=calendar_id,
                    eventId=mapping.external_event_id,
                    body=body,
                ).execute()
            )
            mapping.last_synced_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(f"Updated Google event {mapping.external_event_id} for local event {event.id}")
            return g_event["id"]
        else:
            # Create new Google event
            g_event = await asyncio.to_thread(
                lambda: service.events().insert(
                    calendarId=calendar_id,
                    body=body,
                ).execute()
            )
            google_event_id = g_event["id"]
            db.add(ExternalEventMapping(
                internal_event_id=event.id,
                external_provider=PROVIDER,
                external_event_id=google_event_id,
                external_calendar_id=calendar_id,
            ))
            await db.commit()
            logger.info(f"Created Google event {google_event_id} for local event {event.id}")
            return google_event_id

    except Exception as e:
        logger.error(f"Failed to push event {event.id} to Google: {e}")
        return None


async def delete_from_google(
    external_event_id: str,
    creds: Credentials,
    calendar_id: str = DEFAULT_CALENDAR_ID,
) -> bool:
    """Delete an event from Google Calendar by its Google event ID.

    Returns True on success, False on failure.
    """
    service = _build_calendar_service(creds)
    try:
        await asyncio.to_thread(
            lambda: service.events().delete(
                calendarId=calendar_id,
                eventId=external_event_id,
            ).execute()
        )
        logger.info(f"Deleted Google event {external_event_id}")
        return True
    except Exception as e:
        error_str = str(e)
        # 404/410 = already deleted on Google side — not an error
        if "404" in error_str or "410" in error_str:
            logger.info(f"Google event {external_event_id} already deleted")
            return True
        logger.error(f"Failed to delete Google event {external_event_id}: {e}")
        return False
