"""
Intent parsing service — takes natural language and extracts structured intent + data.

Phase 2 additions:
- recurrence_rule field (RRULE format instead of simple string)
- find_free_slots intent — "when am I free?", "find me 2 hours"
- skip_occurrence intent — "skip this week's standup"
- set_working_hours intent — "my working hours are 9am to 6pm"
"""

import json
import logging
from datetime import datetime
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
                 # set_working_hours, unknown
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = None
    is_all_day: bool = False
    # RRULE string e.g. "FREQ=WEEKLY;BYDAY=MO"
    recurrence_rule: str | None = None
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
- find_free_slots      <- "when am I free?", "find me 2 hours", "what time is available?"
- skip_occurrence      <- "skip this week's standup", "cancel just tomorrow's meeting"
- set_working_hours    <- "my working hours are 9am to 6pm"
- unknown

**IMPORTANT datetime rules:**
- All datetimes MUST include timezone offset matching the user's timezone (e.g., "-05:00")
- Never use bare "Z"
- Resolve relative dates: "tomorrow", "next Monday", "in 2 hours" relative to {current_time}
- Vague times: "morning" -> 09:00, "afternoon" -> 13:00, "evening" -> 18:00, "night" -> 20:00
- Default duration: 1 hour if not specified

**RRULE format for recurring events:**
- "every Monday" -> "FREQ=WEEKLY;BYDAY=MO"
- "every weekday" -> "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
- "daily standup" -> "FREQ=DAILY"
- "every other week" -> "FREQ=WEEKLY;INTERVAL=2"
- "every month on the 1st" -> "FREQ=MONTHLY;BYMONTHDAY=1"

Respond with valid JSON only. Examples:

User: "Schedule a team standup every Monday at 10am for 30 minutes"
{"action": "create_event", "title": "Team standup", "start_time": "2026-03-16T10:00:00-05:00", "end_time": "2026-03-16T10:30:00-05:00", "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO"}

User: "When am I free tomorrow?"
{"action": "find_free_slots", "date_range_start": "2026-03-10T00:00:00-05:00", "date_range_end": "2026-03-10T23:59:59-05:00"}

User: "Find me 2 hours for a meeting this afternoon"
{"action": "find_free_slots", "date_range_start": "2026-03-09T13:00:00-05:00", "date_range_end": "2026-03-09T18:00:00-05:00", "desired_duration_minutes": 120}

User: "My working hours are 9am to 6pm"
{"action": "set_working_hours", "working_hours_start": 9, "working_hours_end": 18}

User: "Skip this week's standup"
{"action": "skip_occurrence", "target_event_query": "standup", "skip_occurrence_date": "2026-03-16T10:00:00-05:00"}

User: "Schedule a team meeting Thursday at 3pm"
{"action": "create_event", "title": "Team meeting", "start_time": "2026-03-12T15:00:00-05:00", "end_time": "2026-03-12T16:00:00-05:00"}

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
