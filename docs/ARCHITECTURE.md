# Maya Calendar Agent — Architecture

> How the code works, end to end.

---

## System Diagram

```
┌─────────────────────────────────────────────────┐
│  User (app.agentmaya.io)                        │
│  "Schedule a team standup every Monday at 10am" │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│  Maya Orchestrator (api.agentmaya.io)            │
│  1. Detects calendar intent (keywords/LLM)       │
│  2. Signs request with HMAC-SHA256               │
│  3. POST /chat to this agent                     │
│  4. Streams response back to user                │
└──────────────────┬───────────────────────────────┘
                   │ HMAC-signed HTTP POST
                   ▼
┌──────────────────────────────────────────────────┐
│  THIS AGENT (maya-calendar, port 8001)           │
│                                                  │
│  ┌─────────────────────────────────────────┐     │
│  │ 1. SECURITY LAYER                       │     │
│  │    Verify HMAC signature + timestamp    │     │
│  │    (app/core/security.py)               │     │
│  └─────────────┬───────────────────────────┘     │
│                ▼                                  │
│  ┌─────────────────────────────────────────┐     │
│  │ 2. USER RESOLUTION                     │     │
│  │    Look up user by agent_user_id       │     │
│  │    or maya_user_id (auto-provision)    │     │
│  │    (app/api/maya.py)                   │     │
│  └─────────────┬───────────────────────────┘     │
│                ▼                                  │
│  ┌─────────────────────────────────────────┐     │
│  │ 3. INTENT PARSER                        │     │
│  │    Send to LLM with system prompt      │     │
│  │    → structured JSON (action + params)  │     │
│  │    (app/services/intent.py)             │     │
│  └─────────────┬───────────────────────────┘     │
│                ▼                                  │
│  ┌─────────────────────────────────────────┐     │
│  │ 4. ACTION HANDLER                       │     │
│  │    Route to correct handler function   │     │
│  │    Execute DB operations               │     │
│  │    (app/services/calendar.py)          │     │
│  └─────────────┬───────────────────────────┘     │
│                ▼                                  │
│  ┌─────────────────────────────────────────┐     │
│  │ 5. RESPONSE                             │     │
│  │    Natural language response string    │     │
│  │    + context tag for follow-ups        │     │
│  │    {"response": "Done! I've ..."}      │     │
│  └─────────────────────────────────────────┘     │
│                                                  │
│  ┌───────────────────┐  ┌──────────────────┐     │
│  │ BACKGROUND WORKERS │  │                  │     │
│  │ • Reminder (60s)   │  │ PostgreSQL DB    │     │
│  │ • Sync push (60s)  │  │ (this agent's    │     │
│  │ • Sync pull (5m)   │  │  own database)   │     │
│  └────────┬──────────┘  └──────────────────┘     │
│           │                                      │
│           ▼                                      │
│  ┌────────────────────┐                          │
│  │ Google Calendar API │                          │
│  │ (bidirectional sync)│                          │
│  └────────────────────┘                          │
└──────────────────────────────────────────────────┘
```

---

## Request Lifecycle (Step by Step)

### 1. Maya Sends a Request

Maya's `agent_caller.py` signs a POST request and sends it to `/chat`:

```
POST /chat
Headers:
  X-Maya-Client-ID: cal_abc123
  X-Maya-Signature: <HMAC-SHA256 of "{timestamp}.{body}">
  X-Maya-Timestamp: 1711936800

Body:
{
  "message": "Schedule a team standup every Monday at 10am",
  "user": {"maya_user_id": 1, "email": "nav@example.com", "name": "Nav"},
  "conversation_history": [...],
  "context": {"agent_user_id": "550e8400-..."}
}
```

### 2. Security Verification (`app/core/security.py`)

The `require_maya_signature` FastAPI dependency:
- Verifies `X-Maya-Client-ID` matches our configured `MAYA_CLIENT_ID`
- Recreates the HMAC: `HMAC-SHA256(MAYA_CLIENT_SECRET, "{timestamp}.{body}")`
- Compares with `X-Maya-Signature` using constant-time comparison
- Rejects if timestamp is older than 5 minutes (replay protection)

### 3. User Resolution (`app/api/maya.py`)

Finds the local user by:
1. **Primary**: UUID lookup by `context.agent_user_id` (returned from prior `/provision` call)
2. **Fallback**: Lookup by `user.maya_user_id`
3. **Auto-provision**: If user doesn't exist, create them on the fly (handles race conditions)

### 4. Intent Parsing (`app/services/intent.py`)

The heart of natural language understanding. Sends the message + conversation history to an LLM with a detailed system prompt.

**What the LLM receives:**
- Current date/time in user's timezone
- The user's timezone name
- Last 6 messages of conversation history (for follow-up resolution)
- A system prompt with all 14+ intent types, RRULE format rules, category definitions, preference keys, and follow-up resolution instructions

**What the LLM returns:**
```json
{
  "action": "create_event",
  "title": "Team standup",
  "category": "work",
  "start_time": "2026-04-06T10:00:00-04:00",
  "end_time": "2026-04-06T10:30:00-04:00",
  "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO"
}
```

**Fallback chain:**
1. LLM returns valid JSON → parse into `ParsedIntent`
2. LLM returns invalid JSON → try `dateparser` library to extract at least a date
3. Everything fails → return `action: "unknown"` with helpful suggestions

**Follow-up resolution:**
When previous assistant messages contain context tags like `[ctx:{"event_id":"...", "title":"..."}]`, the LLM extracts the event ID and uses it to resolve "it", "that", "the meeting" in follow-up messages.

### 5. Action Handling (`app/services/calendar.py`)

The `handle_calendar_action()` function routes to one of 14 handlers:

| Action | Handler | What It Does |
|--------|---------|-------------|
| `create_event` | `_create_event` | Template matching → duration calc → conflict check → create → auto-reminder → queue Google sync |
| `list_events` | `_list_events` | Query date range → expand recurring events → group by day → format |
| `daily_digest` | `_daily_digest` | All events in range → compute stats (meeting hours, free time) → busiest/lightest day |
| `check_availability` | `_check_availability` | Query events in range → report conflicts or "you're free" |
| `find_free_slots` | `_find_free_slots` | All events → compute gaps → filter by working hours → filter by desired duration |
| `update_event` | `_update_event` | Resolve event → apply changes → conflict check at new time → queue sync |
| `delete_event` | `_delete_event` | Resolve event → capture external ID → delete → queue Google delete |
| `skip_occurrence` | `_skip_occurrence` | Find recurring event → create `RecurringEventException` for that date |
| `create_reminder` | `_create_reminder` | Create standalone or event-linked reminder |
| `list_reminders` | `_list_reminders` | Query unsent reminders for user |
| `set_working_hours` | `_set_working_hours` | Update user's working_hours_start/end |
| `search_events` | `_search_events` | Fuzzy title/tag search → past/future direction → count queries |
| `set_preference` | `_set_preference` | Update user's preferences JSON (duration, buffer, templates, etc.) |
| `google_calendar` | `_google_calendar` | Connect/disconnect/import/status for Google Calendar |

### 6. Event Creation Deep Dive

The `_create_event` handler is the most complex. Here's the full flow:

```
User says: "gym tomorrow"
    │
    ▼
Intent parser returns: {action: "create_event", title: "Gym", start_time: "2026-04-02T00:00:00-04:00"}
    │
    ▼
Template matching: "gym" matches → {duration: 60min, category: "health", default_hour: 7}
    │
    ▼
Default hour applied: start_time was midnight (date-only) → moved to 7:00 AM
    │
    ▼
Duration applied: no end_time from LLM → use template's 60 min → end_time = 8:00 AM
    │
    ▼
Category applied: LLM didn't specify → use template's "health"
    │
    ▼
Conflict check: SELECT events WHERE user_id AND overlapping time range
    │
    ├── No conflicts → continue
    └── Conflicts found → still create, but append warning + suggest alternatives
    │
    ▼
Create Event in DB
    │
    ▼
Auto-reminder: if user has default_reminder_minutes preference → create Reminder
    │
    ▼
Queue Google sync: if user has Google connected → create SyncQueueItem
    │
    ▼
Format response: "Done! I've scheduled 💪 Gym for Wed Apr 2, 7:00 – 8:00 AM."
    + context tag: [ctx:{"event_id":"...","title":"Gym","time":"..."}]
```

### 7. Recurring Event Expansion

When listing events, `_get_events_in_range` handles recurring events:

```
1. Query all events in date range (single events)
2. Query all recurring events for the user (regardless of range)
3. For each recurring event:
   a. Parse the RRULE string using dateutil.rrulestr
   b. Expand occurrences within the requested date range
   c. Check RecurringEventExceptions table for skipped dates
   d. Exclude cancelled occurrences
   e. Add remaining occurrences to the event list
4. Sort all events by start_time
5. Return as flat list of (start, end, title, location, category) tuples
```

---

## Background Workers

Two background workers start with the app via FastAPI's lifespan handler in `main.py`:

### Reminder Worker (`reminder_worker.py`)
- **Runs every:** 60 seconds
- **Does:** Queries all reminders where `is_sent=False` and `remind_at <= now`
- **Delivery:** Logs the reminder + POSTs to Maya's `/api/agents/notify` endpoint (HMAC-signed)
- **On success:** Marks `is_sent=True`

### Sync Worker (`sync_worker.py`)
Two concurrent loops:

**Queue Processor (every 60s):**
- Picks up pending `SyncQueueItem` entries (status="pending")
- For create/update: pushes the event to Google Calendar API
- For delete: deletes the event from Google
- Retries up to 3 times on failure
- On startup: resets any items stuck in "processing" from previous crashes

**Pull Scheduler (every 5 min):**
- Finds all users with Google tokens
- For each: calls `pull_from_google()` with their stored sync token
- Uses Google's incremental sync (syncToken) for efficiency
- Falls back to full sync (30 days past → 1 year ahead) if token is expired
- Stores new sync token in user preferences

---

## Database Schema

7 models across 4 migrations:

```
┌──────────┐     ┌─────────────────┐     ┌─────────────────────┐
│  User    │─1:N─│     Event       │─1:N─│ RecurringException  │
│          │     │                 │     └─────────────────────┘
│          │─1:N─│                 │─1:N─┌─────────────────────┐
│          │     └─────────────────┘     │ ExternalEventMapping│
│          │                             └─────────────────────┘
│          │─1:N─┌─────────────────┐
│          │     │    Reminder     │
│          │     └─────────────────┘
│          │─1:1─┌─────────────────┐
│          │     │ GoogleOAuthToken│
│          │     └─────────────────┘
│          │─1:N─┌─────────────────┐
│          │     │  SyncQueueItem  │
└──────────┘     └─────────────────┘
```

### Key Design Decisions

- **UTC storage**: All datetimes stored as UTC. Converted to user's timezone only for display.
- **Encrypted tokens**: Google OAuth tokens encrypted at rest via Fernet (custom SQLAlchemy TypeDecorator on `GoogleOAuthToken`).
- **JSONB preferences**: User preferences stored as a JSONB column — flexible, no migration needed for new preference keys.
- **Async push queue**: Google sync is decoupled — calendar operations return immediately, sync happens asynchronously via `SyncQueueItem`.
- **RRULE strings**: Recurring events store RFC 5545 RRULE strings (e.g., `FREQ=WEEKLY;BYDAY=MO`), expanded at query time using `dateutil.rrulestr`.

---

## Intent Parsing — The 14+ Actions

| # | Action | Trigger Examples | Key Parameters |
|---|--------|-----------------|----------------|
| 1 | `create_event` | "schedule a meeting", "block focus time" | title, start/end_time, recurrence_rule, category |
| 2 | `list_events` | "what's on my calendar?" | date_range_start/end |
| 3 | `check_availability` | "am I free tomorrow afternoon?" | date_range_start/end |
| 4 | `find_free_slots` | "when am I free?", "find me 2 hours" | date_range, desired_duration_minutes |
| 5 | `update_event` | "move the meeting to Friday" | target_event_id/query, new fields |
| 6 | `delete_event` | "cancel the dentist" | target_event_id/query |
| 7 | `skip_occurrence` | "skip this week's standup" | target_event_query, skip_occurrence_date |
| 8 | `create_reminder` | "remind me to call John at 5pm" | reminder_message, remind_at |
| 9 | `list_reminders` | "what reminders do I have?" | — |
| 10 | `set_working_hours` | "my hours are 9am to 6pm" | working_hours_start/end |
| 11 | `search_events` | "when did I last meet with Sarah?" | search_query, search_direction, is_count_query |
| 12 | `set_preference` | "default events to 30 minutes" | preference_key, preference_value |
| 13 | `daily_digest` | "what does my day look like?" | date_range_start/end |
| 14 | `google_calendar` | "connect Google Calendar" | — |
| — | `unknown` | anything else | raw_message (returns helpful suggestions) |

---

## Security Model

1. **HMAC-SHA256 on every request**: Maya signs requests using the agent's `MAYA_CLIENT_SECRET`. The agent verifies before processing.
2. **Timestamp freshness**: Requests older than 5 minutes are rejected (replay protection).
3. **OAuth CSRF protection**: Google OAuth state tokens are signed with HMAC + timestamp + nonce.
4. **Token encryption at rest**: Google OAuth access/refresh tokens encrypted with Fernet before DB storage.
5. **JWT for frontend**: SSO validation generates a JWT for frontend sessions (24-hour expiry).
