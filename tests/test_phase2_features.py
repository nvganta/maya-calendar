"""Tests for Phase 2 features: recurring events, reminders, working hours, free slots."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.event import Event
from app.models.reminder import Reminder
from app.models.recurring_exception import RecurringEventException
from app.services.calendar import handle_calendar_action
from app.services.intent import ParsedIntent


pytestmark = pytest.mark.asyncio


# --- Recurring Events ---

async def test_create_recurring_event(db_session: AsyncSession, test_user: User):
    start = datetime.now(timezone.utc) + timedelta(hours=2)
    intent = ParsedIntent(
        action="create_event",
        title="Daily Standup",
        start_time=start,
        end_time=start + timedelta(minutes=15),
        recurrence_rule="FREQ=DAILY",
        category="work",
        raw_message="daily standup at 10am",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "Daily Standup" in response
    assert "repeats daily" in response.lower()

    result = await db_session.execute(select(Event).where(Event.user_id == test_user.id))
    event = result.scalar_one()
    assert event.recurrence == "FREQ=DAILY"
    assert event.category == "work"


async def test_skip_occurrence(db_session: AsyncSession, test_user: User):
    """Skip a single occurrence of a recurring event."""
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    event = Event(
        user_id=test_user.id,
        title="Weekly Sync",
        start_time=start,
        end_time=start + timedelta(hours=1),
        recurrence="FREQ=WEEKLY;BYDAY=MO",
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    intent = ParsedIntent(
        action="skip_occurrence",
        target_event_query="Weekly Sync",
        skip_occurrence_date=start + timedelta(days=7),
        raw_message="skip next week's sync",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "skipped" in response.lower()
    assert "Weekly Sync" in response

    # Verify exception was created
    result = await db_session.execute(
        select(RecurringEventException).where(RecurringEventException.event_id == event.id)
    )
    exc = result.scalar_one()
    assert exc.is_cancelled is True


# --- Working Hours ---

async def test_set_working_hours(db_session: AsyncSession, test_user: User):
    intent = ParsedIntent(
        action="set_working_hours",
        working_hours_start=9,
        working_hours_end=17,
        raw_message="my working hours are 9am to 5pm",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "9 AM" in response
    assert "5 PM" in response

    await db_session.refresh(test_user)
    assert test_user.working_hours_start == 9
    assert test_user.working_hours_end == 17


async def test_set_working_hours_invalid(db_session: AsyncSession, test_user: User):
    intent = ParsedIntent(
        action="set_working_hours",
        working_hours_start=18,
        working_hours_end=9,
        raw_message="working hours 6pm to 9am",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "don't look right" in response.lower()


# --- Free Slots ---

async def test_find_free_slots(db_session: AsyncSession, test_user: User):
    """Should find free time in a day with events."""
    now = datetime.now(timezone.utc)
    tz_start = now.replace(hour=10, minute=0, second=0, microsecond=0)

    # Create an event in the middle of the day
    event = Event(
        user_id=test_user.id,
        title="Blocker",
        start_time=tz_start + timedelta(hours=2),
        end_time=tz_start + timedelta(hours=3),
    )
    db_session.add(event)
    await db_session.commit()

    intent = ParsedIntent(
        action="find_free_slots",
        date_range_start=tz_start,
        date_range_end=tz_start + timedelta(hours=9),
        desired_duration_minutes=60,
        raw_message="when am I free today",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "free" in response.lower() or "slot" in response.lower()


async def test_find_free_slots_fully_booked(db_session: AsyncSession, test_user: User):
    """When fully booked, should say no slots available."""
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=1)

    # Fill the entire window
    event = Event(
        user_id=test_user.id,
        title="All Day Block",
        start_time=start,
        end_time=start + timedelta(hours=8),
    )
    db_session.add(event)
    await db_session.commit()

    intent = ParsedIntent(
        action="find_free_slots",
        date_range_start=start,
        date_range_end=start + timedelta(hours=8),
        desired_duration_minutes=60,
        raw_message="find me an hour",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "fully booked" in response.lower() or "no" in response.lower()
