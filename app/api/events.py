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
from app.models.reminder import Reminder
from app.models.user import User
from app.schemas.event import (
    EventCreate,
    EventUpdate,
    EventResponse,
    ReminderCreate,
    ReminderResponse,
)

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
    recurring_result = await db.execute(
        select(Event).where(
            Event.user_id == user.id,
            Event.recurrence.isnot(None),
        )
    )
    recurring_events = recurring_result.scalars().all()

    if recurring_events:
        from dateutil.rrule import rrulestr

        for event in recurring_events:
            try:
                rule = rrulestr(event.recurrence, dtstart=event.start_time)
                duration = event.end_time - event.start_time
                occurrences = rule.between(start, end, inc=True)
                for occ_start in occurrences:
                    # Skip the original occurrence (already in non-recurring results
                    # if it falls in range)
                    if occ_start == event.start_time:
                        if event not in events:
                            events.append(event)
                        continue
                    # Create a virtual event for this occurrence
                    virtual = Event(
                        id=event.id,
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

    await db.delete(event)
    await db.commit()
