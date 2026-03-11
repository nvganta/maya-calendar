"""Tests for the calendar business logic (create, list, update, delete, availability)."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.event import Event
from app.models.reminder import Reminder
from app.services.calendar import handle_calendar_action
from app.services.intent import ParsedIntent


pytestmark = pytest.mark.asyncio


# --- Create Event ---

async def test_create_event(db_session: AsyncSession, test_user: User):
    now = datetime.now(timezone.utc)
    intent = ParsedIntent(
        action="create_event",
        title="Lunch with Sarah",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
        location="Olive Garden",
        raw_message="Schedule lunch with Sarah at Olive Garden",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "Lunch with Sarah" in response
    assert "Olive Garden" in response

    # Verify event was actually created in DB
    result = await db_session.execute(select(Event).where(Event.user_id == test_user.id))
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].title == "Lunch with Sarah"
    assert events[0].location == "Olive Garden"


async def test_create_event_default_duration(db_session: AsyncSession, test_user: User):
    """When no end_time is provided, default to 1 hour."""
    start = datetime.now(timezone.utc) + timedelta(hours=2)
    intent = ParsedIntent(
        action="create_event",
        title="Quick call",
        start_time=start,
        raw_message="Schedule a quick call",
    )
    await handle_calendar_action(intent, test_user, db_session)

    result = await db_session.execute(select(Event).where(Event.user_id == test_user.id))
    event = result.scalar_one()
    # SQLite strips timezone info, so compare naive values
    expected_end = (start + timedelta(hours=1)).replace(tzinfo=None)
    actual_end = event.end_time.replace(tzinfo=None) if event.end_time.tzinfo else event.end_time
    assert abs((actual_end - expected_end).total_seconds()) < 2


async def test_create_event_missing_fields(db_session: AsyncSession, test_user: User):
    intent = ParsedIntent(action="create_event", raw_message="schedule something")
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "title" in response.lower() or "time" in response.lower()


async def test_create_event_conflict_warning(db_session: AsyncSession, test_user: User, sample_events):
    """Creating an event that overlaps with an existing one should warn."""
    # sample_events[0] starts in 1 hour — schedule something overlapping
    overlapping_start = sample_events[0].start_time + timedelta(minutes=15)
    intent = ParsedIntent(
        action="create_event",
        title="Conflicting Meeting",
        start_time=overlapping_start,
        end_time=overlapping_start + timedelta(hours=1),
        raw_message="schedule conflicting meeting",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "Conflicting Meeting" in response
    assert "Team Standup" in response  # should mention the conflicting event


# --- List Events ---

async def test_list_events(db_session: AsyncSession, test_user: User, sample_events):
    now = datetime.now(timezone.utc)
    intent = ParsedIntent(
        action="list_events",
        date_range_start=now,
        date_range_end=now + timedelta(days=7),
        raw_message="what's on my calendar",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "Team Standup" in response
    assert "Dentist Appointment" in response
    assert "Team Meeting" in response


async def test_list_events_empty(db_session: AsyncSession, test_user: User):
    now = datetime.now(timezone.utc)
    intent = ParsedIntent(
        action="list_events",
        date_range_start=now,
        date_range_end=now + timedelta(days=7),
        raw_message="what's on my calendar",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "clear" in response.lower() or "nothing" in response.lower()


# --- Check Availability ---

async def test_check_availability_free(db_session: AsyncSession, test_user: User):
    """Should report as free when no events in range."""
    far_future = datetime.now(timezone.utc) + timedelta(days=30)
    intent = ParsedIntent(
        action="check_availability",
        date_range_start=far_future,
        date_range_end=far_future + timedelta(hours=2),
        raw_message="am I free",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "free" in response.lower()


async def test_check_availability_busy(db_session: AsyncSession, test_user: User, sample_events):
    """Should list conflicts when events exist in range."""
    intent = ParsedIntent(
        action="check_availability",
        date_range_start=sample_events[0].start_time - timedelta(minutes=10),
        date_range_end=sample_events[0].end_time + timedelta(minutes=10),
        raw_message="am I free",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "Team Standup" in response


# --- Update Event ---

async def test_update_event_time(db_session: AsyncSession, test_user: User, sample_events):
    new_start = sample_events[0].start_time + timedelta(hours=2)
    original_duration = sample_events[0].end_time - sample_events[0].start_time

    intent = ParsedIntent(
        action="update_event",
        target_event_query="Team Standup",
        start_time=new_start,
        raw_message="move team standup to later",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "Updated" in response
    assert "Team Standup" in response

    # Verify the event was actually updated
    await db_session.refresh(sample_events[0])
    assert sample_events[0].start_time == new_start
    # Duration should be preserved
    assert sample_events[0].end_time == new_start + original_duration


async def test_update_event_not_found(db_session: AsyncSession, test_user: User):
    intent = ParsedIntent(
        action="update_event",
        target_event_query="nonexistent meeting",
        raw_message="move nonexistent meeting",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "couldn't find" in response.lower()


# --- Delete Event ---

async def test_delete_event(db_session: AsyncSession, test_user: User, sample_events):
    intent = ParsedIntent(
        action="delete_event",
        target_event_query="Dentist",
        raw_message="cancel the dentist",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "Dentist Appointment" in response
    assert "cancelled" in response.lower()

    # Verify deletion
    result = await db_session.execute(
        select(Event).where(Event.title == "Dentist Appointment")
    )
    assert result.scalar_one_or_none() is None


# --- Reminders ---

async def test_create_reminder(db_session: AsyncSession, test_user: User):
    remind_at = datetime.now(timezone.utc) + timedelta(hours=5)
    intent = ParsedIntent(
        action="create_reminder",
        reminder_message="Call John",
        remind_at=remind_at,
        raw_message="remind me to call john at 5pm",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "Call John" in response

    result = await db_session.execute(select(Reminder).where(Reminder.user_id == test_user.id))
    reminder = result.scalar_one()
    assert reminder.message == "Call John"
    assert reminder.is_sent is False


async def test_list_reminders_empty(db_session: AsyncSession, test_user: User):
    intent = ParsedIntent(action="list_reminders", raw_message="what reminders do I have")
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "don't have any" in response.lower() or "no" in response.lower()


# --- Unknown Intent ---

async def test_unknown_intent(db_session: AsyncSession, test_user: User):
    intent = ParsedIntent(action="unknown", raw_message="what's the meaning of life")
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "schedule" in response.lower() or "calendar" in response.lower()
