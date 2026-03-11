"""
Calendar business logic — takes a parsed intent and executes the corresponding action.

Phase 2: Recurring events (RRULE expansion), availability intelligence,
         skip-occurrence exceptions, working hours, free-slot finder.
"""

import uuid
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.event import Event
from app.models.reminder import Reminder
from app.models.recurring_exception import RecurringEventException
from app.services.intent import ParsedIntent, DEFAULT_TIMEZONE


async def handle_calendar_action(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    handlers = {
        "create_event":       _create_event,
        "list_events":        _list_events,
        "check_availability": _check_availability,
        "find_free_slots":    _find_free_slots,
        "update_event":       _update_event,
        "delete_event":       _delete_event,
        "skip_occurrence":    _skip_occurrence,
        "create_reminder":    _create_reminder,
        "list_reminders":     _list_reminders,
        "set_working_hours":  _set_working_hours,
    }

    handler = handlers.get(intent.action)
    if not handler:
        return (
            "I'm not sure what you'd like me to do. You can ask me to:\n"
            "- **Schedule** -- \"Team meeting tomorrow at 3pm\"\n"
            "- **Recurring** -- \"Every Monday standup at 10am\"\n"
            "- **Availability** -- \"Find me 2 free hours this afternoon\"\n"
            "- **Update/Cancel** -- \"Move the standup to 11am\" / \"Cancel Friday's meeting\"\n"
            "- **Skip** -- \"Skip this week's standup\"\n"
            "- **Reminders** -- \"Remind me to call John at 5pm\"\n"
            "- **Working hours** -- \"My working hours are 9am to 6pm\""
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

    conflicts = await _find_overlapping_events(db, user.id, intent.start_time, end_time)

    event = Event(
        user_id=user.id,
        title=intent.title,
        description=intent.description,
        start_time=intent.start_time,
        end_time=end_time,
        location=intent.location,
        is_all_day=intent.is_all_day,
        recurrence=intent.recurrence_rule,
        tags=intent.tags,
    )
    db.add(event)
    await db.commit()

    time_str = _format_time_range(intent.start_time, end_time, tz)
    location_str = f" at {intent.location}" if intent.location else ""
    recurrence_str = _describe_rrule(intent.recurrence_rule) if intent.recurrence_rule else ""
    response = f"Done! I've scheduled **{intent.title}**{location_str} for {time_str}.{recurrence_str}"

    if conflicts:
        conflict_names = ", ".join(f"**{e.title}**" for e in conflicts)
        response += f"\n\nNote: This overlaps with {conflict_names}."

    return response


async def _list_events(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    tz = _user_tz(user)
    now = datetime.now(tz)

    start = intent.date_range_start or now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = intent.date_range_end or (start + timedelta(days=7))

    all_events = await _get_events_in_range(db, user, start, end)

    if not all_events:
        period = _describe_period(start, end, tz)
        return f"Your calendar is clear {period}. Nothing scheduled!"

    lines = []
    current_day = None
    for (event_start, event_end, title, location, _) in all_events:
        event_day = event_start.astimezone(tz).date()
        if event_day != current_day:
            current_day = event_day
            lines.append(f"\n**{_format_day_label(event_day, now.date())}**")
        time_str = _format_time_range(event_start, event_end, tz)
        location_str = f" ({location})" if location else ""
        lines.append(f"  - {time_str} -- **{title}**{location_str}")

    period = _describe_period(start, end, tz)
    return f"Here's what you have {period}:" + "\n".join(lines)


async def _check_availability(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    tz = _user_tz(user)
    start, end = intent.date_range_start, intent.date_range_end

    if not start or not end:
        return "Which time period should I check? For example, \"Am I free tomorrow afternoon?\""

    all_events = await _get_events_in_range(db, user, start, end)

    if not all_events:
        return f"You're free {_format_time_range(start, end, tz)}! Want me to schedule something?"

    lines = [f"You have {len(all_events)} event(s) during that time:\n"]
    for (event_start, event_end, title, _, __) in all_events:
        lines.append(f"  - **{title}** -- {_format_time_range(event_start, event_end, tz)}")
    return "\n".join(lines)


async def _find_free_slots(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    tz = _user_tz(user)
    now = datetime.now(tz)

    start = intent.date_range_start or now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = intent.date_range_end or (start + timedelta(days=1))
    desired_mins = intent.desired_duration_minutes or 30

    all_events = await _get_events_in_range(db, user, start, end)
    free_slots = _compute_free_slots(all_events, start, end, user, tz, desired_mins)

    if not free_slots:
        return f"You're fully booked -- no {_format_duration(desired_mins)}+ slots available then."

    lines = [f"Free slots ({_format_duration(desired_mins)}+ available):\n"]
    for (slot_start, slot_end) in free_slots[:8]:
        lines.append(f"  - {_format_time_range(slot_start, slot_end, tz)}")
    if len(free_slots) > 8:
        lines.append(f"  (and {len(free_slots) - 8} more)")
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
            lines.append(f"  {i}. **{e.title}** -- {_format_time_range(e.start_time, e.end_time, tz)}")
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
        changes.append("location updated")

    if intent.description is not None:
        event.description = intent.description

    if intent.recurrence_rule is not None:
        event.recurrence = intent.recurrence_rule
        changes.append(f"recurrence updated")

    if not changes:
        return f"Found **{event.title}** but I'm not sure what to change. What would you like to update?"

    await db.commit()
    return f"Updated **{event.title}** -- {', '.join(changes)}."


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
            lines.append(f"  {i}. **{e.title}** -- {_format_time_range(e.start_time, e.end_time, tz)}")
        return "\n".join(lines)

    event = matches[0]
    title = event.title
    time_str = _format_time_range(event.start_time, event.end_time, tz)
    await db.delete(event)
    await db.commit()

    if event.recurrence:
        return f"Done -- cancelled **{title}** and all its future occurrences."
    return f"Done -- **{title}** ({time_str}) has been cancelled."


async def _skip_occurrence(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    tz = _user_tz(user)

    if not intent.target_event_query:
        return "Which recurring event's occurrence would you like to skip?"

    matches = await _find_events_by_query(db, user.id, intent.target_event_query, recurring_only=True)
    if not matches:
        return f"I couldn't find a recurring event matching \"{intent.target_event_query}\"."
    if len(matches) > 1:
        lines = [f"Found {len(matches)} recurring events. Which one?\n"]
        for i, e in enumerate(matches[:5], 1):
            lines.append(f"  {i}. **{e.title}** ({_describe_rrule(e.recurrence).strip()})")
        return "\n".join(lines)

    event = matches[0]
    if intent.skip_occurrence_date:
        exception_date = intent.skip_occurrence_date.astimezone(tz).date()
    else:
        exception_date = _next_occurrence_date(event, tz)
        if not exception_date:
            return f"Could not find the next occurrence of **{event.title}**."

    existing = await db.execute(
        select(RecurringEventException).where(
            and_(RecurringEventException.event_id == event.id,
                 RecurringEventException.exception_date == exception_date)
        )
    )
    if existing.scalars().first():
        return f"The **{event.title}** occurrence on {exception_date.strftime('%A, %b %d')} is already skipped."

    db.add(RecurringEventException(
        event_id=event.id, user_id=user.id,
        exception_date=exception_date, is_cancelled=True,
    ))
    await db.commit()

    day_str = _format_day_label(exception_date, datetime.now(tz).date())
    return f"Done -- skipped the **{event.title}** occurrence on {day_str}."


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
        lines.append(f"  - **{r.message}** -- {day_str} at {_format_time_short(r.remind_at, tz)}")
    return "\n".join(lines)


async def _set_working_hours(intent: ParsedIntent, user: User, db: AsyncSession) -> str:
    if intent.working_hours_start is None or intent.working_hours_end is None:
        return "What are your working hours? For example, \"My working hours are 9am to 6pm.\""

    s, e = intent.working_hours_start, intent.working_hours_end
    if not (0 <= s <= 23 and 0 <= e <= 23 and s < e):
        return "Those hours don't look right. Please try again with a format like \"9am to 6pm\"."

    user.working_hours_start = s
    user.working_hours_end = e
    await db.commit()
    return f"Got it! Working hours set to **{_fmt_hour(s)} -- {_fmt_hour(e)}**."


# ---------------------------------------------------------------------------
# Recurring event expansion
# ---------------------------------------------------------------------------

async def _get_events_in_range(
    db: AsyncSession, user: User, start: datetime, end: datetime
) -> list[tuple[datetime, datetime, str, str | None, str | None]]:
    """Return all (start, end, title, location, category) tuples in the range, expanding recurrences."""
    result = await db.execute(
        select(Event).where(
            and_(
                Event.user_id == user.id,
                or_(
                    and_(Event.recurrence.is_(None), Event.start_time < end, Event.end_time > start),
                    Event.recurrence.isnot(None),
                )
            )
        )
    )
    events = result.scalars().all()

    recurring_ids = [e.id for e in events if e.recurrence]
    exceptions_by_event: dict[uuid.UUID, set[date]] = {}
    if recurring_ids:
        exc_result = await db.execute(
            select(RecurringEventException).where(
                and_(
                    RecurringEventException.event_id.in_(recurring_ids),
                    RecurringEventException.is_cancelled == True,  # noqa: E712
                )
            )
        )
        for exc in exc_result.scalars().all():
            exceptions_by_event.setdefault(exc.event_id, set()).add(exc.exception_date)

    output: list[tuple[datetime, datetime, str, str | None, str | None]] = []

    for event in events:
        if not event.recurrence:
            output.append((event.start_time, event.end_time, event.title, event.location, None))
        else:
            duration = event.end_time - event.start_time
            cancelled = exceptions_by_event.get(event.id, set())
            try:
                rule = rrulestr(event.recurrence, dtstart=event.start_time)
                for occ in rule.between(start, end, inc=True):
                    if occ.date() not in cancelled:
                        output.append((occ, occ + duration, event.title, event.location, None))
            except Exception:
                if event.start_time < end and event.end_time > start:
                    output.append((event.start_time, event.end_time, event.title, event.location, None))

    output.sort(key=lambda x: x[0])
    return output


# ---------------------------------------------------------------------------
# Availability & free-slot computation
# ---------------------------------------------------------------------------

def _compute_free_slots(
    busy: list[tuple],
    range_start: datetime,
    range_end: datetime,
    user: User,
    tz: ZoneInfo,
    min_duration_minutes: int,
) -> list[tuple[datetime, datetime]]:
    min_delta = timedelta(minutes=min_duration_minutes)
    free_slots: list[tuple[datetime, datetime]] = []

    current_day = range_start.astimezone(tz).date()
    last_day = range_end.astimezone(tz).date()

    while current_day <= last_day:
        day_start = datetime(current_day.year, current_day.month, current_day.day,
                             user.working_hours_start, 0, 0, tzinfo=tz)
        day_end = datetime(current_day.year, current_day.month, current_day.day,
                           user.working_hours_end, 0, 0, tzinfo=tz)

        window_start = max(day_start, range_start)
        window_end = min(day_end, range_end)

        if window_start >= window_end:
            current_day += timedelta(days=1)
            continue

        day_busy = sorted(
            [(max(s, window_start), min(e, window_end))
             for (s, e, *_) in busy
             if s < window_end and e > window_start],
            key=lambda x: x[0],
        )

        cursor = window_start
        for (b_start, b_end) in day_busy:
            if b_start > cursor and (b_start - cursor) >= min_delta:
                free_slots.append((cursor, b_start))
            cursor = max(cursor, b_end)

        if window_end > cursor and (window_end - cursor) >= min_delta:
            free_slots.append((cursor, window_end))

        current_day += timedelta(days=1)

    return free_slots


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
    recurring_only: bool = False,
) -> list[Event]:
    now = datetime.now(timezone.utc)
    conditions = [Event.user_id == user_id, Event.title.ilike(f"%{query}%")]
    if recurring_only:
        conditions.append(Event.recurrence.isnot(None))
    result = await db.execute(
        select(Event).where(and_(*conditions))
        .order_by((Event.start_time >= now).desc(), Event.start_time)
        .limit(5)
    )
    return list(result.scalars().all())


def _next_occurrence_date(event: Event, tz: ZoneInfo) -> date | None:
    if not event.recurrence:
        return None
    try:
        now = datetime.now(tz)
        rule = rrulestr(event.recurrence, dtstart=event.start_time)
        occ = rule.after(now)
        return occ.date() if occ else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _user_tz(user: User) -> ZoneInfo:
    return ZoneInfo(user.timezone or DEFAULT_TIMEZONE)


def _format_time_range(start: datetime, end: datetime, tz: ZoneInfo) -> str:
    s = start.astimezone(tz)
    e = end.astimezone(tz)
    if s.date() == e.date():
        return f"{s.strftime('%b %d')}, {s.strftime('%I:%M %p').lstrip('0')} - {e.strftime('%I:%M %p').lstrip('0')}"
    return f"{s.strftime('%b %d, %I:%M %p').lstrip('0')} - {e.strftime('%b %d, %I:%M %p').lstrip('0')}"


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


def _describe_rrule(rrule_str: str | None) -> str:
    if not rrule_str:
        return ""
    mapping = {
        "FREQ=DAILY":                         " It repeats daily.",
        "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR":  " It repeats every weekday.",
        "FREQ=WEEKLY;BYDAY=MO":               " It repeats every Monday.",
        "FREQ=WEEKLY;BYDAY=TU":               " It repeats every Tuesday.",
        "FREQ=WEEKLY;BYDAY=WE":               " It repeats every Wednesday.",
        "FREQ=WEEKLY;BYDAY=TH":               " It repeats every Thursday.",
        "FREQ=WEEKLY;BYDAY=FR":               " It repeats every Friday.",
        "FREQ=WEEKLY;INTERVAL=2":             " It repeats every other week.",
        "FREQ=MONTHLY":                       " It repeats monthly.",
        "FREQ=YEARLY":                        " It repeats annually.",
    }
    return mapping.get(rrule_str.upper(), f" (repeats: {rrule_str})")


def _format_duration(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if m else f"{h}h"


def _fmt_hour(h: int) -> str:
    if h == 0:   return "12 AM"
    if h == 12:  return "12 PM"
    return f"{h} AM" if h < 12 else f"{h - 12} PM"
