"""
Calendar business logic — takes a parsed intent and executes the corresponding action.
"""

import uuid
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.event import Event
from app.models.reminder import Reminder
from app.services.intent import ParsedIntent, DEFAULT_TIMEZONE


async def handle_calendar_action(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    handlers = {
        "create_event":       _create_event,
        "list_events":        _list_events,
        "check_availability": _check_availability,
        "update_event":       _update_event,
        "delete_event":       _delete_event,
        "create_reminder":    _create_reminder,
        "list_reminders":     _list_reminders,
    }

    handler = handlers.get(intent.action)
    if not handler:
        return (
            "I'm not sure what you'd like me to do. You can ask me to:\n"
            "- **Schedule** — \"Team meeting tomorrow at 3pm\"\n"
            "- **View** — \"What's on my calendar this week?\"\n"
            "- **Check** — \"Am I free tomorrow afternoon?\"\n"
            "- **Update** — \"Move the standup to 11am\"\n"
            "- **Cancel** — \"Cancel the dentist appointment\"\n"
            "- **Remind** — \"Remind me to call John at 5pm\""
        )

    return await handler(intent, user, db)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

async def _create_event(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    if not intent.title or not intent.start_time:
        return "I need at least a title and a time. Could you give me more details?"

    tz = _user_tz(user)
    end_time = intent.end_time or (intent.start_time + timedelta(hours=1))

    # Check for conflicts
    conflicts = await _find_overlapping_events(db, user.id, intent.start_time, end_time)

    event = Event(
        user_id=user.id,
        title=intent.title,
        description=intent.description,
        start_time=intent.start_time,
        end_time=end_time,
        location=intent.location,
        is_all_day=intent.is_all_day,
        recurrence=intent.recurrence,
        tags=intent.tags,
    )
    db.add(event)
    await db.commit()

    time_str = _format_time_range(intent.start_time, end_time, tz)
    location_str = f" at {intent.location}" if intent.location else ""
    response = f"Done! I've scheduled **{intent.title}**{location_str} for {time_str}."

    if conflicts:
        conflict_names = ", ".join(f"**{e.title}**" for e in conflicts)
        response += f"\n\n⚠️ Note: This overlaps with {conflict_names}."

    return response


async def _list_events(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    tz = _user_tz(user)
    now = datetime.now(tz)

    start = intent.date_range_start or now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = intent.date_range_end or (start + timedelta(days=7))

    result = await db.execute(
        select(Event).where(
            and_(Event.user_id == user.id, Event.start_time < end, Event.end_time > start)
        ).order_by(Event.start_time)
    )
    events = result.scalars().all()

    if not events:
        period = _describe_period(start, end, tz)
        return f"Your calendar is clear {period}. Nothing scheduled!"

    lines = []
    current_day = None
    for event in events:
        event_day = event.start_time.astimezone(tz).date()
        if event_day != current_day:
            current_day = event_day
            lines.append(f"\n**{_format_day_label(event_day, now.date())}**")
        time_str = _format_time_range(event.start_time, event.end_time, tz)
        location_str = f" 📍 {event.location}" if event.location else ""
        lines.append(f"  • {time_str} — **{event.title}**{location_str}")

    period = _describe_period(start, end, tz)
    return f"Here's what you have {period}:" + "\n".join(lines)


async def _check_availability(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    tz = _user_tz(user)
    start, end = intent.date_range_start, intent.date_range_end

    if not start or not end:
        return "Which time period should I check? For example, \"Am I free tomorrow afternoon?\""

    result = await db.execute(
        select(Event).where(
            and_(Event.user_id == user.id, Event.start_time < end, Event.end_time > start)
        )
    )
    events = result.scalars().all()

    if not events:
        return f"You're free {_format_time_range(start, end, tz)}! Want me to schedule something?"

    lines = [f"You have {len(events)} event(s) during that time:\n"]
    for event in events:
        lines.append(f"  • **{event.title}** — {_format_time_range(event.start_time, event.end_time, tz)}")
    return "\n".join(lines)


async def _update_event(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    tz = _user_tz(user)

    if not intent.target_event_query:
        return "Which event would you like to update?"

    matches = await _find_events_by_query(db, user.id, intent.target_event_query)
    if not matches:
        return f"I couldn't find an event matching \"{intent.target_event_query}\"."
    if len(matches) > 1:
        lines = [f"Found {len(matches)} matching events. Which one?\n"]
        for i, e in enumerate(matches[:5], 1):
            lines.append(f"  {i}. **{e.title}** — {_format_time_range(e.start_time, e.end_time, tz)}")
        return "\n".join(lines)

    event = matches[0]
    changes = []

    if intent.title and intent.title != event.title:
        old = event.title
        event.title = intent.title
        changes.append(f"renamed from \"{old}\"")

    if intent.start_time:
        duration = (event.end_time - event.start_time) if event.end_time else timedelta(hours=1)
        event.start_time = intent.start_time
        event.end_time = intent.end_time or (intent.start_time + duration)
        changes.append(f"moved to {_format_time_range(event.start_time, event.end_time, tz)}")
    elif intent.end_time:
        event.end_time = intent.end_time
        changes.append(f"ends at {_format_time_short(event.end_time, tz)}")

    if intent.location is not None:
        event.location = intent.location
        changes.append(f"location → {intent.location}" if intent.location else "location removed")

    if intent.description is not None:
        event.description = intent.description

    if intent.recurrence is not None:
        event.recurrence = intent.recurrence
        changes.append("recurrence updated")

    if not changes:
        return f"Found **{event.title}** but I'm not sure what to change. What would you like to update?"

    await db.commit()
    return f"Updated **{event.title}** — {', '.join(changes)}."


async def _delete_event(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    tz = _user_tz(user)

    if not intent.target_event_query:
        return "Which event would you like to cancel?"

    matches = await _find_events_by_query(db, user.id, intent.target_event_query)
    if not matches:
        return f"I couldn't find an event matching \"{intent.target_event_query}\"."
    if len(matches) > 1:
        lines = [f"Found {len(matches)} matches. Which one should I cancel?\n"]
        for i, e in enumerate(matches[:5], 1):
            lines.append(f"  {i}. **{e.title}** — {_format_time_range(e.start_time, e.end_time, tz)}")
        return "\n".join(lines)

    event = matches[0]
    title = event.title
    time_str = _format_time_range(event.start_time, event.end_time, tz)
    await db.delete(event)
    await db.commit()
    return f"Done — **{title}** ({time_str}) has been cancelled."


async def _create_reminder(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    tz = _user_tz(user)
    if not intent.reminder_message or not intent.remind_at:
        return "I need a message and a time. For example, \"Remind me to call John at 5pm.\""

    db.add(Reminder(user_id=user.id, message=intent.reminder_message, remind_at=intent.remind_at))
    await db.commit()

    time_str = _format_time_short(intent.remind_at, tz)
    day_str = _format_day_label(intent.remind_at.astimezone(tz).date(), datetime.now(tz).date())
    return f"Reminder set! I'll remind you to **{intent.reminder_message}** on {day_str} at {time_str}."


async def _list_reminders(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    tz = _user_tz(user)
    result = await db.execute(
        select(Reminder)
        .where(and_(Reminder.user_id == user.id, Reminder.is_sent == False))  # noqa: E712
        .order_by(Reminder.remind_at)
    )
    reminders = result.scalars().all()
    if not reminders:
        return "You don't have any pending reminders."

    lines = ["Here are your upcoming reminders:\n"]
    for r in reminders:
        day_str = _format_day_label(r.remind_at.astimezone(tz).date(), datetime.now(tz).date())
        lines.append(f"  • **{r.message}** — {day_str} at {_format_time_short(r.remind_at, tz)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

async def _find_overlapping_events(
    db: AsyncSession, user_id: uuid.UUID, start: datetime, end: datetime
) -> list[Event]:
    result = await db.execute(
        select(Event).where(
            and_(Event.user_id == user_id, Event.start_time < end, Event.end_time > start)
        )
    )
    return list(result.scalars().all())


async def _find_events_by_query(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
) -> list[Event]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Event).where(and_(Event.user_id == user_id, Event.title.ilike(f"%{query}%")))
        .order_by((Event.start_time >= now).desc(), Event.start_time)
        .limit(5)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _user_tz(user: User) -> ZoneInfo:
    return ZoneInfo(user.timezone or DEFAULT_TIMEZONE)


def _format_time_range(start: datetime, end: datetime, tz: ZoneInfo) -> str:
    s = start.astimezone(tz)
    e = end.astimezone(tz)
    if s.date() == e.date():
        return f"{s.strftime('%b %d')}, {s.strftime('%I:%M %p').lstrip('0')} – {e.strftime('%I:%M %p').lstrip('0')}"
    return f"{s.strftime('%b %d, %I:%M %p').lstrip('0')} – {e.strftime('%b %d, %I:%M %p').lstrip('0')}"


def _format_time_short(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime('%I:%M %p').lstrip('0')


def _format_day_label(d: date, today: date) -> str:
    diff = (d - today).days
    if diff == 0:   return "Today"
    if diff == 1:   return "Tomorrow"
    if diff == -1:  return "Yesterday"
    if 2 <= diff <= 6: return d.strftime("%A")
    return d.strftime("%a, %b %d")


def _describe_period(start: datetime, end: datetime, tz: ZoneInfo) -> str:
    s = start.astimezone(tz).date()
    e = end.astimezone(tz).date()
    today = datetime.now(tz).date()
    if s == e:
        return f"for {_format_day_label(s, today).lower()}"
    if s == today and (e - s).days == 7:
        return "this week"
    return f"from {_format_day_label(s, today)} to {_format_day_label(e, today)}"


def _format_duration(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if m else f"{h}h"
