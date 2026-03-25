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
                 # set_working_hours, search_events, set_preference, daily_digest, unknown
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

    # For updates/deletes — ID from conversation context tag, or title for fuzzy search
    target_event_id: str | None = None
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
- daily_digest         ← "what does my day look like?", "what about tomorrow?", "how's my week?", "give me a rundown of today"
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

User: "What does my day look like?"
{{"action": "daily_digest", "date_range_start": "2026-03-09T00:00:00-05:00", "date_range_end": "2026-03-09T23:59:59-05:00"}}

User: "What about tomorrow?"
{{"action": "daily_digest", "date_range_start": "2026-03-10T00:00:00-05:00", "date_range_end": "2026-03-10T23:59:59-05:00"}}

User: "How's my week?"
{{"action": "daily_digest", "date_range_start": "2026-03-09T00:00:00-05:00", "date_range_end": "2026-03-15T23:59:59-05:00"}}

User: "My working hours are 9am to 6pm"
{{"action": "set_working_hours", "working_hours_start": 9, "working_hours_end": 18}}

User: "Skip this week's standup"
{{"action": "skip_occurrence", "target_event_query": "standup", "skip_occurrence_date": "2026-03-16T10:00:00-05:00"}}

**FOLLOW-UP REFERENCES — resolving "it", "that", "the meeting":**

When the user says "cancel that", "make it 4pm", "add a reminder for it", etc., look at the
most recent assistant message in conversation history. If it contains a context tag like
[ctx:{{"event_id":"<uuid>","title":"<title>","time":"<iso>"}}], extract the JSON and use it:

- Set "target_event_id" to the event_id from the tag
- Set "target_event_query" to the title from the tag
- Parse the user's actual intent (delete_event, update_event, create_reminder, etc.)

If no context tag is present, extract the event name from **bold** text in the previous
assistant message and use it as "target_event_query".

Follow-up examples (assuming previous assistant message contained a context tag):

Previous assistant: "Done! I've scheduled **Team Meeting** for Thu Mar 26, 3:00 – 4:00 PM.\n[ctx:{{"event_id":"a1b2c3d4-e5f6-7890-abcd-ef1234567890","title":"Team Meeting","time":"2026-03-26T15:00:00-05:00"}}]"

User: "cancel that"
{{"action": "delete_event", "target_event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "target_event_query": "Team Meeting"}}

User: "make it 4pm instead"
{{"action": "update_event", "target_event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "target_event_query": "Team Meeting", "start_time": "2026-03-26T16:00:00-05:00"}}

User: "add a reminder for it 30 minutes before"
{{"action": "create_reminder", "target_event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "reminder_message": "Team Meeting", "remind_at": "2026-03-26T14:30:00-05:00"}}

User: "change the location to Room 5"
{{"action": "update_event", "target_event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "target_event_query": "Team Meeting", "location": "Room 5"}}

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
        elif settings.LLM_PROVIDER == "anthropic":
            response_text = await _call_anthropic(system, messages, settings.ANTHROPIC_API_KEY)
        else:
            raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}. Must be 'openai' or 'anthropic'.")

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
    except Exception as e:
        logger.exception(f"Intent parsing infrastructure error: {e}")
        raise


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
    client = AsyncOpenAI(api_key=api_key, timeout=15.0)
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
    client = AsyncAnthropic(api_key=api_key, timeout=15.0)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        system=system,
        messages=messages,
        temperature=0,
        max_tokens=600,
    )
    return response.content[0].text
