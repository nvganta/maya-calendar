"""Tests for Phase 3 features: preferences, templates, search, daily digest, conversation context."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.event import Event
from app.models.reminder import Reminder
from app.services.calendar import handle_calendar_action
from app.services.intent import ParsedIntent


pytestmark = pytest.mark.asyncio


# --- Preferences ---

async def test_set_preference_default_duration(db_session: AsyncSession, test_user: User):
    intent = ParsedIntent(
        action="set_preference",
        preference_key="default_duration",
        preference_value="45",
        raw_message="default events to 45 minutes",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "45 min" in response
    await db_session.refresh(test_user)
    assert test_user.preferences["default_duration_minutes"] == 45


async def test_set_preference_buffer(db_session: AsyncSession, test_user: User):
    intent = ParsedIntent(
        action="set_preference",
        preference_key="buffer",
        preference_value="10",
        raw_message="add 10 minute buffer",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "10 min" in response
    await db_session.refresh(test_user)
    assert test_user.preferences["buffer_minutes"] == 10


async def test_set_preference_no_meeting_before(db_session: AsyncSession, test_user: User):
    intent = ParsedIntent(
        action="set_preference",
        preference_key="no_meeting_before",
        preference_value="10",
        raw_message="no meetings before 10am",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "10 AM" in response
    await db_session.refresh(test_user)
    assert test_user.preferences["no_meeting_before"] == 10


async def test_set_preference_unknown_key(db_session: AsyncSession, test_user: User):
    intent = ParsedIntent(
        action="set_preference",
        preference_key="unknown_thing",
        preference_value="42",
        raw_message="set unknown thing",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "don't recognize" in response.lower()


# --- Default Duration Applied ---

async def test_default_duration_applied_on_create(db_session: AsyncSession, test_user: User):
    """User sets 30-min default, then creates an event without end_time."""
    # Set preference first
    test_user.preferences = {"default_duration_minutes": 30}
    await db_session.commit()

    start = datetime.now(timezone.utc) + timedelta(hours=2)
    intent = ParsedIntent(
        action="create_event",
        title="Quick Sync",
        start_time=start,
        raw_message="quick sync",
    )
    await handle_calendar_action(intent, test_user, db_session)

    result = await db_session.execute(select(Event).where(Event.title == "Quick Sync"))
    event = result.scalar_one()
    actual_duration = (event.end_time - event.start_time).total_seconds() / 60
    assert abs(actual_duration - 30) < 1


# --- Event Templates ---

async def test_system_template_standup(db_session: AsyncSession, test_user: User):
    """'standup' should get 15-min duration and 'work' category from system template."""
    start = datetime.now(timezone.utc) + timedelta(hours=2)
    intent = ParsedIntent(
        action="create_event",
        title="Morning Standup",
        start_time=start,
        raw_message="schedule morning standup",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    result = await db_session.execute(select(Event).where(Event.title == "Morning Standup"))
    event = result.scalar_one()
    duration_mins = (event.end_time - event.start_time).total_seconds() / 60
    assert abs(duration_mins - 15) < 1
    assert event.category == "work"


async def test_system_template_gym(db_session: AsyncSession, test_user: User):
    """'gym' should get 60-min duration and 'health' category."""
    start = datetime.now(timezone.utc) + timedelta(hours=2)
    intent = ParsedIntent(
        action="create_event",
        title="Gym",
        start_time=start,
        raw_message="schedule gym",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    result = await db_session.execute(select(Event).where(Event.title == "Gym"))
    event = result.scalar_one()
    duration_mins = (event.end_time - event.start_time).total_seconds() / 60
    assert abs(duration_mins - 60) < 1
    assert event.category == "health"


# --- Search ---

async def test_search_events_by_title(db_session: AsyncSession, test_user: User):
    now = datetime.now(timezone.utc)
    event = Event(
        user_id=test_user.id,
        title="Dentist Checkup",
        start_time=now - timedelta(days=5),
        end_time=now - timedelta(days=5) + timedelta(hours=1),
    )
    db_session.add(event)
    await db_session.commit()

    intent = ParsedIntent(
        action="search_events",
        search_query="dentist",
        search_direction="past",
        raw_message="when was my last dentist appointment",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "Dentist Checkup" in response


async def test_search_events_not_found(db_session: AsyncSession, test_user: User):
    intent = ParsedIntent(
        action="search_events",
        search_query="nonexistent",
        search_direction="past",
        raw_message="when did I last have nonexistent",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "no events found" in response.lower()


async def test_search_next_event(db_session: AsyncSession, test_user: User):
    """'What's my next event?' with no search query."""
    now = datetime.now(timezone.utc)
    event = Event(
        user_id=test_user.id,
        title="Upcoming Call",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
    )
    db_session.add(event)
    await db_session.commit()

    intent = ParsedIntent(
        action="search_events",
        search_direction="future",
        raw_message="what's my next event",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "Upcoming Call" in response


# --- Daily Digest ---

async def test_daily_digest_empty(db_session: AsyncSession, test_user: User):
    now = datetime.now(timezone.utc)
    far_future = now + timedelta(days=30)
    intent = ParsedIntent(
        action="daily_digest",
        date_range_start=far_future.replace(hour=0, minute=0, second=0),
        date_range_end=far_future.replace(hour=23, minute=59, second=59),
        raw_message="what does my day look like",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "nothing scheduled" in response.lower() or "free" in response.lower() or "clear" in response.lower()


async def test_daily_digest_with_events(db_session: AsyncSession, test_user: User):
    now = datetime.now(timezone.utc)
    # Use a future day to avoid events bleeding across midnight boundary
    day_start = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    for i, title in enumerate(["Standup", "Design Review", "Lunch"]):
        db_session.add(Event(
            user_id=test_user.id,
            title=title,
            start_time=day_start + timedelta(hours=i * 2),
            end_time=day_start + timedelta(hours=i * 2 + 1),
        ))
    await db_session.commit()

    intent = ParsedIntent(
        action="daily_digest",
        date_range_start=day_start,
        date_range_end=day_start.replace(hour=23, minute=59, second=59),
        raw_message="what does my day look like",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "3 event(s)" in response
    assert "Standup" in response
    assert "scheduled" in response
    assert "free" in response


async def test_daily_digest_week(db_session: AsyncSession, test_user: User):
    now = datetime.now(timezone.utc)
    # Add events on 2 different days
    db_session.add(Event(
        user_id=test_user.id, title="Monday Meeting",
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=2),
    ))
    db_session.add(Event(
        user_id=test_user.id, title="Wednesday Call",
        start_time=now + timedelta(days=2, hours=1),
        end_time=now + timedelta(days=2, hours=2),
    ))
    await db_session.commit()

    intent = ParsedIntent(
        action="daily_digest",
        date_range_start=now,
        date_range_end=now + timedelta(days=7),
        raw_message="how's my week",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "2 event(s)" in response
    assert "2 day(s)" in response
    assert "busiest" in response or "free" in response


# --- Conversation Context ---

async def test_context_tag_in_create_response(db_session: AsyncSession, test_user: User):
    """Create event response should include a [ctx:...] tag."""
    start = datetime.now(timezone.utc) + timedelta(hours=2)
    intent = ParsedIntent(
        action="create_event",
        title="Team Sync",
        start_time=start,
        end_time=start + timedelta(hours=1),
        raw_message="schedule team sync",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "[ctx:" in response
    assert '"event_id"' in response
    assert '"title"' in response
    assert "Team Sync" in response


async def test_resolve_event_by_id(db_session: AsyncSession, test_user: User):
    """Delete using target_event_id should resolve by exact UUID."""
    now = datetime.now(timezone.utc)
    event = Event(
        user_id=test_user.id,
        title="To Delete",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    intent = ParsedIntent(
        action="delete_event",
        target_event_id=str(event.id),
        target_event_query="To Delete",
        raw_message="cancel that",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "cancelled" in response.lower()
    result = await db_session.execute(select(Event).where(Event.id == event.id))
    assert result.scalar_one_or_none() is None


async def test_resolve_event_id_not_found(db_session: AsyncSession, test_user: User):
    """When target_event_id points to a deleted event, should NOT fall back to fuzzy search."""
    import uuid
    intent = ParsedIntent(
        action="delete_event",
        target_event_id=str(uuid.uuid4()),  # nonexistent
        target_event_query="some event",
        raw_message="cancel that",
    )
    response = await handle_calendar_action(intent, test_user, db_session)
    assert "couldn't find" in response.lower() or "deleted" in response.lower()


async def test_reminder_linked_to_event(db_session: AsyncSession, test_user: User):
    """'Add a reminder for it' should link the reminder to the event."""
    now = datetime.now(timezone.utc)
    event = Event(
        user_id=test_user.id,
        title="Important Meeting",
        start_time=now + timedelta(hours=5),
        end_time=now + timedelta(hours=6),
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    intent = ParsedIntent(
        action="create_reminder",
        target_event_id=str(event.id),
        raw_message="add a reminder for it",
    )
    response = await handle_calendar_action(intent, test_user, db_session)

    assert "Important Meeting" in response

    result = await db_session.execute(select(Reminder).where(Reminder.user_id == test_user.id))
    reminder = result.scalar_one()
    assert reminder.event_id == event.id
    assert reminder.message == "Important Meeting"
