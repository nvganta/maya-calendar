"""
Direct CRUD endpoints for the calendar frontend (calendar.agentmaya.io).
All endpoints require JWT auth via SSO.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.event import Event
from app.models.external_event_mapping import ExternalEventMapping
from app.models.reminder import Reminder
from app.models.user import User
from app.schemas.event import (
    EventCreate,
    EventUpdate,
    EventResponse,
    ReminderCreate,
    ReminderResponse,
)
from app.services.calendar import queue_google_sync

router = APIRouter()


# --- Reminders (must be before /{event_id} to avoid route shadowing) ---


@router.get("/reminders/pending", response_model=list[ReminderResponse])
async def list_reminders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List unsent reminders."""
    result = await db.execute(
        select(Reminder)
        .where(Reminder.user_id == user.id, Reminder.is_sent.is_(False))
        .order_by(Reminder.remind_at)
    )
    return result.scalars().all()


@router.post("/reminders", response_model=ReminderResponse, status_code=201)
async def create_reminder(
    body: ReminderCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a reminder."""
    if body.event_id is not None:
        ev_result = await db.execute(
            select(Event).where(Event.id == body.event_id, Event.user_id == user.id)
        )
        if ev_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Event not found")

    reminder = Reminder(
        user_id=user.id,
        event_id=body.event_id,
        message=body.message,
        remind_at=body.remind_at,
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return reminder


@router.delete("/reminders/{reminder_id}", status_code=204)
async def delete_reminder(
    reminder_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a reminder."""
    result = await db.execute(
        select(Reminder).where(
            Reminder.id == reminder_id, Reminder.user_id == user.id
        )
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    await db.delete(reminder)
    await db.commit()


# --- Events ---


@router.get("", response_model=list[EventResponse])
async def list_events(
    start: datetime = Query(..., description="Range start (ISO 8601)"),
    end: datetime = Query(..., description="Range end (ISO 8601)"),
    category: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List events within a date range, including expanded recurring occurrences."""
    import uuid as uuid_mod
    from dateutil.rrule import rrulestr
    from app.models.recurring_exception import RecurringEventException

    # Ensure start/end are timezone-aware to avoid aware-vs-naive comparison errors
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    filters = [
        Event.user_id == user.id,
        Event.start_time < end,
        Event.end_time > start,
    ]
    if category:
        filters.append(Event.category == category)

    # Non-recurring events in range
    non_recurring_filters = filters + [Event.recurrence.is_(None)]
    result = await db.execute(
        select(Event).where(and_(*non_recurring_filters)).order_by(Event.start_time)
    )
    events = list(result.scalars().all())

    # Recurring events: fetch all for this user and expand occurrences into range
    recurring_filters = [
        Event.user_id == user.id,
        Event.recurrence.isnot(None),
    ]
    if category:
        recurring_filters.append(Event.category == category)

    recurring_result = await db.execute(
        select(Event).where(*recurring_filters)
    )
    recurring_events = list(recurring_result.scalars().all())

    if recurring_events:
        # Load cancelled occurrences so we can skip them
        recurring_ids = [e.id for e in recurring_events]
        exc_result = await db.execute(
            select(RecurringEventException).where(
                RecurringEventException.event_id.in_(recurring_ids),
                RecurringEventException.is_cancelled.is_(True),
            )
        )
        cancelled_dates: dict[uuid.UUID, set] = {}
        for exc in exc_result.scalars().all():
            cancelled_dates.setdefault(exc.event_id, set()).add(exc.exception_date)

        for event in recurring_events:
            event_cancelled = cancelled_dates.get(event.id, set())
            try:
                rule = rrulestr(event.recurrence, dtstart=event.start_time)
                duration = event.end_time - event.start_time
                occurrences = rule.between(start, end, inc=True)
                for occ_start in occurrences:
                    # Skip cancelled occurrences
                    if occ_start.date() in event_cancelled:
                        continue
                    # Original occurrence: use the real DB row
                    if occ_start == event.start_time:
                        if event not in events:
                            events.append(event)
                        continue
                    # Virtual occurrence: deterministic ID so React gets stable keys
                    virtual = Event(
                        id=uuid_mod.uuid5(event.id, occ_start.isoformat()),
                        user_id=event.user_id,
                        title=event.title,
                        description=event.description,
                        start_time=occ_start,
                        end_time=occ_start + duration,
                        location=event.location,
                        is_all_day=event.is_all_day,
                        recurrence=event.recurrence,
                        tags=event.tags,
                        category=event.category,
                        created_at=event.created_at,
                        updated_at=event.updated_at,
                    )
                    events.append(virtual)
            except (ValueError, TypeError):
                # Invalid RRULE, include the base event if it overlaps
                if event.start_time < end and event.end_time > start:
                    events.append(event)

    events.sort(key=lambda e: e.start_time)
    return events


@router.post("", response_model=EventResponse, status_code=201)
async def create_event(
    body: EventCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new event."""
    event = Event(
        user_id=user.id,
        title=body.title,
        description=body.description,
        start_time=body.start_time,
        end_time=body.end_time,
        location=body.location,
        is_all_day=body.is_all_day,
        recurrence=body.recurrence,
        tags=body.tags,
        category=body.category,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    await queue_google_sync(db, user, "create", event_id=event.id)
    return event


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single event by ID."""
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.user_id == user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing event (partial)."""
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.user_id == user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(event, field, value)

    event.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(event)
    await queue_google_sync(db, user, "update", event_id=event.id)
    return event


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an event."""
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.user_id == user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Capture external ID before deleting (mapping cascades with event)
    ext_result = await db.execute(
        select(ExternalEventMapping.external_event_id).where(and_(
            ExternalEventMapping.internal_event_id == event_id,
            ExternalEventMapping.external_provider == "google",
        ))
    )
    ext_id = ext_result.scalar_one_or_none()

    await db.delete(event)
    await db.commit()

    if ext_id:
        await queue_google_sync(db, user, "delete", external_event_id=ext_id)
