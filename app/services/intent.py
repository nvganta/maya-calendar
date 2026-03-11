"""
Intent parsing service — takes natural language and extracts structured intent + data.
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
                 # create_reminder, list_reminders, unknown
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = None
    is_all_day: bool = False
    recurrence: str | None = None
    tags: list[str] | None = None

    # For updates/deletes
    target_event_query: str | None = None

    # For reminders
    reminder_message: str | None = None
    remind_at: datetime | None = None

    # For list queries and availability
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None

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
- unknown

**IMPORTANT datetime rules:**
- All datetimes MUST include timezone offset matching the user's timezone (e.g., "-05:00")
- Never use bare "Z"
- Resolve relative dates: "tomorrow", "next Monday", "in 2 hours" relative to {current_time}
- Vague times: "morning" → 09:00, "afternoon" → 13:00, "evening" → 18:00, "night" → 20:00
- Default duration: 1 hour if not specified

Respond with valid JSON only. Examples:

User: "Schedule a team meeting Thursday at 3pm"
{{"action": "create_event", "title": "Team meeting", "start_time": "2026-03-12T15:00:00-05:00", "end_time": "2026-03-12T16:00:00-05:00"}}

User: "What's on my calendar this week?"
{{"action": "list_events", "date_range_start": "2026-03-09T00:00:00-05:00", "date_range_end": "2026-03-15T23:59:59-05:00"}}

User: "Am I free tomorrow afternoon?"
{{"action": "check_availability", "date_range_start": "2026-03-10T13:00:00-05:00", "date_range_end": "2026-03-10T18:00:00-05:00"}}

User: "Move the team meeting to Friday"
{{"action": "update_event", "target_event_query": "team meeting", "start_time": "2026-03-13T15:00:00-05:00"}}

User: "Cancel the dentist appointment"
{{"action": "delete_event", "target_event_query": "dentist"}}

User: "Remind me to call John at 5pm"
{{"action": "create_reminder", "reminder_message": "Call John", "remind_at": "2026-03-09T17:00:00-05:00"}}

User: "What reminders do I have?"
{{"action": "list_reminders"}}

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
    for field in ("start_time", "end_time", "remind_at", "date_range_start", "date_range_end"):
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
