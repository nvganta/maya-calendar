"""
Intent parsing service — takes natural language and extracts structured intent + data.

Phase 3 additions:
- category field on events (work, personal, focus, health)
- search_events intent (NL search by title/tags, past/future, count)
- set_preference intent (default duration, buffer, no-meeting-before, preferred times)
"""

import json
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import dateparser
from pydantic import BaseModel

from app.core.config import get_settings
from app.schemas.maya import ConversationMessage

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "America/New_York"


class ParsedIntent(BaseModel):
    """Structured output from intent parsing."""
    action: str  # create_event, list_events, check_availability, update_event, delete_event,
                 # create_reminder, list_reminders, find_free_slots, skip_occurrence,
                 # set_working_hours, search_events, set_preference, unknown
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = None
    is_all_day: bool = False
    # RRULE string e.g. "FREQ=WEEKLY;BYDAY=MO"
    recurrence_rule: str | None = None
    # Event category: "work", "personal", "focus", "health"
    category: str | None = None
    tags: list[str] | None = None

    # For updates/deletes
    target_event_query: str | None = None

    # For reminders
    reminder_message: str | None = None
    remind_at: datetime | None = None

    # For list queries and availability
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None

    # For find_free_slots
    desired_duration_minutes: int | None = None

    # For skip_occurrence
    skip_occurrence_date: datetime | None = None

    # For set_working_hours
    working_hours_start: int | None = None
    working_hours_end: int | None = None

    # For search_events — "when did I last meet with Sarah?", "what's my next event?"
    search_query: str | None = None
    search_direction: str | None = None  # "past" or "future"
    is_count_query: bool = False          # "how many meetings last week?"

    # For set_preference — "I prefer meetings in the afternoon", "add 15 min buffer"
    preference_key: str | None = None    # "default_duration", "buffer", "no_meeting_before",
                                         # "preferred_meeting_start", "preferred_meeting_end",
                                         # "default_reminder", "custom_template"
    preference_value: str | None = None  # raw value string

    # Raw fallback
    raw_message: str = ""


SYSTEM_PROMPT = """You are an intent parser for a calendar agent. Given a user message, extract structured intent.

Current date/time: {current_time}
User's timezone: {user_timezone}

**action** must be one of:
- create_event
- list_events
- check_availability
- update_event
- delete_event
- create_reminder
- list_reminders
- find_free_slots      ← "when am I free?", "find me 2 hours", "what time is available?"
- skip_occurrence      ← "skip this week's standup", "cancel just tomorrow's meeting"
- set_working_hours    ← "my working hours are 9am to 6pm"
- search_events        ← "when did I last meet with Sarah?", "what's my next event?", "how many meetings last week?"
- set_preference       ← "I prefer meetings in the afternoon", "add 15 min buffer between meetings", "default events to 30 minutes"
- unknown

**IMPORTANT datetime rules:**
- All datetimes MUST include timezone offset matching the user's timezone (e.g., "-05:00")
- Never use bare "Z"
- Resolve relative dates: "tomorrow", "next Monday", "in 2 hours" relative to {current_time}
- Vague times: "morning" → 09:00, "afternoon" → 13:00, "evening" → 18:00, "night" → 20:00
- Default duration: 1 hour if not specified

**category** (optional, include when clear):
- "focus"    → "focus time", "deep work", "no interruptions", "heads-down"
- "work"     → meetings, standups, calls, reviews
- "personal" → lunch, errands, appointments, social
- "health"   → gym, workout, doctor, dentist, run, yoga

**RRULE format for recurring events:**
- "every Monday" → "FREQ=WEEKLY;BYDAY=MO"
- "every weekday" → "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
- "daily standup" → "FREQ=DAILY"
- "every other week" → "FREQ=WEEKLY;INTERVAL=2"
- "every month on the 1st" → "FREQ=MONTHLY;BYMONTHDAY=1"

**set_preference keys:**
- "default_duration"         ← "default my events to 30 minutes"
- "buffer"                   ← "add 15 min buffer between meetings"
- "no_meeting_before"        ← "no meetings before 10am" (value = hour as string, e.g. "10")
- "preferred_meeting_start"  ← "I prefer meetings after 2pm" (value = hour as string)
- "preferred_meeting_end"    ← "no meetings after 5pm" (value = hour as string)
- "default_reminder"         ← "remind me 30 minutes before events by default" (value = minutes as string)
- "custom_template"          ← "when I say gym, create a 1-hour health event at 7am"
                               (value = JSON string: {{"keyword":"gym","duration":60,"category":"health","default_hour":7}})

Respond with valid JSON only. Examples:

User: "Block 2 hours of focus time tomorrow afternoon"
{{"action": "create_event", "title": "Focus Time", "category": "focus", "start_time": "2026-03-10T13:00:00-05:00", "end_time": "2026-03-10T15:00:00-05:00"}}

User: "Schedule a team standup every Monday at 10am for 30 minutes"
{{"action": "create_event", "title": "Team standup", "category": "work", "start_time": "2026-03-16T10:00:00-05:00", "end_time": "2026-03-16T10:30:00-05:00", "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO"}}

User: "Schedule gym tomorrow at 7am"
{{"action": "create_event", "title": "Gym", "category": "health", "start_time": "2026-03-10T07:00:00-05:00", "end_time": "2026-03-10T08:00:00-05:00"}}

User: "When did I last have a dentist appointment?"
{{"action": "search_events", "search_query": "dentist", "search_direction": "past"}}

User: "What's my next meeting?"
{{"action": "search_events", "search_query": "meeting", "search_direction": "future"}}

User: "How many meetings did I have last week?"
{{"action": "search_events", "search_query": "meeting", "date_range_start": "2026-03-02T00:00:00-05:00", "date_range_end": "2026-03-08T23:59:59-05:00", "is_count_query": true}}

User: "What's my next event?"
{{"action": "search_events", "search_direction": "future"}}

User: "I prefer meetings in the afternoon"
{{"action": "set_preference", "preference_key": "preferred_meeting_start", "preference_value": "13"}}

User: "Add 15 minute buffer between my meetings"
{{"action": "set_preference", "preference_key": "buffer", "preference_value": "15"}}

User: "Default event duration to 30 minutes"
{{"action": "set_preference", "preference_key": "default_duration", "preference_value": "30"}}

User: "No meetings before 10am"
{{"action": "set_preference", "preference_key": "no_meeting_before", "preference_value": "10"}}

User: "When am I free tomorrow?"
{{"action": "find_free_slots", "date_range_start": "2026-03-10T00:00:00-05:00", "date_range_end": "2026-03-10T23:59:59-05:00"}}

User: "Find me 2 hours for deep work this afternoon"
{{"action": "find_free_slots", "category": "focus", "date_range_start": "2026-03-09T13:00:00-05:00", "date_range_end": "2026-03-09T18:00:00-05:00", "desired_duration_minutes": 120}}

User: "My working hours are 9am to 6pm"
{{"action": "set_working_hours", "working_hours_start": 9, "working_hours_end": 18}}

User: "Skip this week's standup"
{{"action": "skip_occurrence", "target_event_query": "standup", "skip_occurrence_date": "2026-03-16T10:00:00-05:00"}}

FOLLOW-UP CONTEXT: Use conversation history to resolve references like "make it 4pm instead", "cancel that", "add a reminder for it".

Only output JSON. No explanation."""


async def parse_intent(
    message: str,
    conversation_history: list[ConversationMessage] | None = None,
    user_timezone: str | None = None,
) -> ParsedIntent:
    """Parse user message into a structured calendar intent using an LLM."""
    settings = get_settings()
    tz_name = user_timezone or DEFAULT_TIMEZONE
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)

    messages = []
    if conversation_history:
        for msg in conversation_history[-6:]:
            messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": message})

    system = SYSTEM_PROMPT.format(
        current_time=now.isoformat(),
        user_timezone=tz_name,
    )

    try:
        if settings.LLM_PROVIDER == "openai":
            response_text = await _call_openai(system, messages, settings.OPENAI_API_KEY)
        else:
            response_text = await _call_anthropic(system, messages, settings.ANTHROPIC_API_KEY)

        response_text = _strip_code_fences(response_text)
        data = json.loads(response_text)
        data["raw_message"] = message
        intent = ParsedIntent(**data)
        intent = _ensure_timezone_aware(intent, tz)
        return intent

    except json.JSONDecodeError as e:
        logger.warning(f"LLM returned invalid JSON: {e}")
        return _fallback_parse(message, tz)
    except (ValueError, KeyError) as e:
        logger.warning(f"Intent parsing failed: {e}")
        return ParsedIntent(action="unknown", raw_message=message)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _ensure_timezone_aware(intent: ParsedIntent, tz: ZoneInfo) -> ParsedIntent:
    for field in ("start_time", "end_time", "remind_at", "date_range_start", "date_range_end", "skip_occurrence_date"):
        val = getattr(intent, field)
        if val is not None and val.tzinfo is None:
            setattr(intent, field, val.replace(tzinfo=tz))
    return intent


def _fallback_parse(message: str, tz: ZoneInfo) -> ParsedIntent:
    parsed_date = dateparser.parse(
        message,
        settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": True, "TIMEZONE": str(tz)},
    )
    if parsed_date:
        return ParsedIntent(action="unknown", raw_message=message, start_time=parsed_date)
    return ParsedIntent(action="unknown", raw_message=message)


async def _call_openai(system: str, messages: list[dict], api_key: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}] + messages,
        temperature=0,
        max_tokens=600,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


async def _call_anthropic(system: str, messages: list[dict], api_key: str) -> str:
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        system=system,
        messages=messages,
        temperature=0,
        max_tokens=600,
    )
    return response.content[0].text
