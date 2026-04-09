# Maya Calendar Agent

This is the Calendar Agent for Maya — an AI assistant hub where users talk to a central assistant (Maya) and Maya routes requests to specialized agents. This agent handles everything calendar-related: scheduling events, checking availability, setting reminders, managing recurring meetings, syncing with Google Calendar, and providing daily/weekly digests — all through natural conversation.

Users never call this agent directly. Maya forwards messages here when it detects calendar-related intent.

> For detailed documentation, see the `docs/` folder:
> - `docs/OVERVIEW.md` — What this is, capabilities, quick start
> - `docs/ARCHITECTURE.md` — System diagram, request lifecycle, deep dives
> - `docs/INTEGRATION.md` — Step-by-step guide to connect to Maya
> - `docs/API.md` — All HTTP endpoints with request/response examples
> - `docs/PHASES.md` — Development roadmap and current status
> - `docs/RESEARCH.md` — Competitive research on calendar apps

---

## How This Agent Fits Into Maya

Maya is the hub. This agent is a spoke. Here's the flow:

1. User sends a message to Maya: "Schedule a meeting with the team on Thursday at 3pm"
2. Maya detects calendar intent (via keywords or LLM classification)
3. Maya forwards the message to this agent's `/chat` endpoint with user context
4. This agent processes it (parses intent via LLM, executes action, checks conflicts, etc.)
5. This agent returns a response string
6. Maya streams it back to the user

This agent has its own database, its own users table (linked to Maya via `maya_user_id`), and its own logic. It's a fully independent service.

### Keywords Maya Uses to Route Here

`calendar, schedule, meeting, appointment, event, remind, reminder, free, busy, availability, reschedule, cancel meeting, book, time slot, agenda, week, tomorrow, today`

---

## Maya Integration Contract

### 1. Provision Endpoint (required)

```
POST /api/maya/provision
```

Called when a user clicks "Connect" on this agent in Maya's marketplace.

**Request from Maya:**
```json
{
  "maya_user_id": 1,
  "email": "user@example.com",
  "name": "User Name"
}
```

**Headers Maya sends:**
```
Content-Type: application/json
X-Maya-Client-ID: <this agent's client_id>
X-Maya-Signature: <HMAC-SHA256 signature>
X-Maya-Timestamp: <unix timestamp>
```

**HMAC Verification:**
Maya signs requests using this agent's `client_secret` as the HMAC key. To verify:
```python
message = f"{timestamp}.{body}"
expected = hmac.new(client_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
hmac.compare_digest(signature, expected)
```
Reject if timestamp is older than 5 minutes.

**Response:**
```json
{
  "agent_user_id": "550e8400-e29b-41d4-a716-446655440000",
  "needs_setup": false
}
```

`needs_setup` is `false` because this agent doesn't require external account linking. Users can start using it immediately after connecting. Google Calendar sync is optional and can be connected later via chat.

### 2. Chat Endpoint (required)

```
POST /chat
```

Called every time Maya routes a calendar message to this agent.

**Request from Maya:**
```json
{
  "message": "Am I free Thursday afternoon?",
  "user": {
    "maya_user_id": 1,
    "email": "user@example.com",
    "name": "User Name"
  },
  "conversation_history": [
    {"role": "user", "content": "previous message"},
    {"role": "assistant", "content": "previous response"}
  ],
  "context": {
    "agent_user_id": "550e8400-..."
  }
}
```

**Response:**
```json
{
  "response": "You're free Thursday afternoon! Want me to schedule something?"
}
```

Just a response string. Maya handles streaming it to the user.

The response may contain a context tag at the end (e.g., `[ctx:{"event_id":"...","title":"..."}]`) which the intent parser uses to resolve follow-ups like "cancel that" or "make it 4pm instead".

### 3. SSO (for the frontend)

When a user clicks "Open Calendar" in Maya:
1. Maya generates a short-lived token and redirects to this agent's frontend with `?sso_token=...`
2. The frontend sends the token to `POST /api/sso/validate`
3. This backend calls Maya's `POST /api/sso/validate` with the token + `client_id` + `client_secret`
4. Maya returns user info if valid
5. This agent issues a JWT for frontend sessions (24-hour expiry)

---

## Tech Stack

- **Backend:** Python 3.11+, FastAPI (async), SQLAlchemy 2.0 (async), PostgreSQL, Alembic
- **LLM:** OpenAI (gpt-4o-mini) or Anthropic (claude-haiku) for intent parsing
- **Google Sync:** google-api-python-client, google-auth-oauthlib (OAuth 2.0)
- **Background Workers:** asyncio tasks (reminder worker every 60s, sync worker every 60s/5min)
- **Deployment:** Render.com (Python runtime) via `render.yaml`
- **Frontend (future):** Next.js at `calendar.agentmaya.io` (accessed via SSO from Maya)

## Project Structure

```
maya-calendar/
├── CLAUDE.md              # You are here
├── docs/                  # Detailed documentation
│   ├── OVERVIEW.md        # Capabilities, quick start
│   ├── ARCHITECTURE.md    # System diagram, request lifecycle, deep dives
│   ├── INTEGRATION.md     # How to connect to Maya
│   ├── API.md             # Endpoint reference
│   ├── PHASES.md          # Roadmap + current status
│   └── RESEARCH.md        # Competitive research
├── requirements.txt       # Python dependencies
├── render.yaml            # Render.com deployment config
├── alembic.ini            # Alembic config
├── alembic/               # Database migrations (4 versions)
│   ├── env.py
│   └── versions/
│       ├── 001_initial_schema.py
│       ├── 5ab497d5b544_phase_2_*.py
│       ├── c9d348162306_phase_3_*.py
│       └── d4a1b2c3d4e5_phase_4_*.py
├── app/
│   ├── main.py            # FastAPI entry point + lifespan (background workers)
│   ├── core/
│   │   ├── config.py      # Pydantic Settings (all env vars)
│   │   ├── database.py    # Async SQLAlchemy engine + session factory
│   │   ├── security.py    # HMAC-SHA256 verification
│   │   └── auth.py        # JWT creation/verification for frontend SSO
│   ├── models/
│   │   ├── user.py        # User (maya_user_id, timezone, working_hours, preferences JSONB)
│   │   ├── event.py       # Event (RRULE recurrence, tags ARRAY, category)
│   │   ├── reminder.py    # Reminder (event-linked or standalone)
│   │   ├── google_oauth_token.py   # Encrypted Google OAuth tokens (Fernet)
│   │   ├── recurring_exception.py  # Skip/reschedule individual occurrences
│   │   ├── external_event_mapping.py  # Local <-> Google event ID mapping
│   │   └── sync_queue_item.py     # Async push queue for Google sync
│   ├── schemas/
│   │   ├── maya.py        # Maya integration DTOs (provision, chat)
│   │   └── event.py       # Event/reminder request/response schemas
│   ├── api/
│   │   ├── maya.py        # POST /api/maya/provision + POST /chat
│   │   ├── events.py      # Direct CRUD endpoints (stubs, for future frontend)
│   │   ├── google.py      # Google OAuth flow (auth-url, callback, disconnect, status)
│   │   └── sso.py         # SSO validation + JWT issuance
│   └── services/
│       ├── intent.py      # LLM-based intent parser (14+ actions)
│       ├── calendar.py    # Calendar business logic (1,300+ lines, all action handlers)
│       ├── google_auth.py # Google OAuth 2.0 (consent URL, token exchange, refresh, revoke)
│       ├── google_sync.py # Bidirectional Google Calendar sync (pull + push)
│       ├── reminder_worker.py  # Background: checks due reminders every 60s
│       └── sync_worker.py     # Background: push queue (60s) + pull scheduler (5min)
└── tests/                 # Test suite (1,000+ lines)
    ├── conftest.py        # Fixtures (in-memory SQLite, test user, sample events)
    ├── test_calendar_service.py   # Core CRUD tests
    ├── test_formatting.py         # Time/date formatting tests
    ├── test_phase2_features.py    # Recurring, skip, working hours, free slots
    ├── test_phase3_features.py    # Preferences, templates, search, digest
    └── test_security.py           # HMAC verification tests
```

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server
uvicorn app.main:app --reload --port 8001

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Run tests
pytest tests/ -v
```

Port 8001 to avoid conflict with Maya's backend on 8000.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection (this agent's own DB, not Maya's) |
| `MAYA_CLIENT_ID` | Yes | From Maya admin panel when registering this agent |
| `MAYA_CLIENT_SECRET` | Yes | From Maya admin panel (shown once, save immediately) |
| `MAYA_API_URL` | Yes | Maya's backend URL (`http://localhost:8000` for dev) |
| `LLM_PROVIDER` | Yes | `"openai"` or `"anthropic"` |
| `OPENAI_API_KEY` | If openai | OpenAI API key for intent parsing |
| `ANTHROPIC_API_KEY` | If anthropic | Anthropic API key for intent parsing |
| `JWT_SECRET_KEY` | Yes | Random hex string for frontend JWT sessions |
| `GOOGLE_CLIENT_ID` | No | Google OAuth (sync disabled without it) |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth (sync disabled without it) |
| `GOOGLE_REDIRECT_URI` | No | Defaults to `http://localhost:8001/api/google/callback` |
| `TOKEN_ENCRYPTION_KEY` | No | Fernet key for encrypting Google tokens at rest |

## Data Models (7 total)

### User
- `id` (UUID, PK), `maya_user_id` (int, unique), `email`, `name`
- `timezone` (string, default "America/New_York")
- `working_hours_start` / `working_hours_end` (int, default 9/18)
- `preferences` (JSONB — default_duration, buffer, no_meeting_before, custom_templates, etc.)

### Event
- `id` (UUID, PK), `user_id` (FK -> User)
- `title`, `description`, `location`
- `start_time`, `end_time` (TZ-aware datetimes, stored as UTC)
- `is_all_day` (bool), `recurrence` (RRULE string, e.g., "FREQ=WEEKLY;BYDAY=MO")
- `tags` (ARRAY of strings), `category` (work/personal/focus/health)
- Indexed on `(user_id, start_time)` and `(user_id, end_time)`

### Reminder
- `id` (UUID, PK), `event_id` (FK, optional — can be standalone), `user_id` (FK)
- `message`, `remind_at` (TZ-aware), `is_sent` (bool)
- Indexed on `(user_id, is_sent, remind_at)`

### GoogleOAuthToken
- `user_id` (FK, 1:1), `access_token`, `refresh_token` (both encrypted via Fernet)
- `token_expires_at`, `google_email`, `scopes`

### RecurringEventException
- `event_id` (FK), `user_id` (FK), `exception_date`, `is_cancelled`
- Tracks skipped or rescheduled individual occurrences

### ExternalEventMapping
- `internal_event_id` (FK -> Event), `external_provider` ("google"), `external_event_id`
- Links local events to Google Calendar events for bidirectional sync

### SyncQueueItem
- `user_id` (FK), `event_id` (FK, optional), `action` (create/update/delete)
- `status` (pending/processing/completed/failed), `retry_count`, `error_message`
- Async push queue — calendar operations return immediately, sync happens in background

## Intent Parsing (14+ Actions)

The LLM classifies user messages into structured intents:

| Intent | Example | Action |
|--------|---------|--------|
| `create_event` | "Schedule a meeting Thursday at 3pm" | Template match → duration calc → conflict check → create |
| `list_events` | "What's on my calendar this week?" | Query + expand recurring → group by day → format |
| `check_availability` | "Am I free tomorrow afternoon?" | Query time range → report conflicts or "you're free" |
| `find_free_slots` | "Find me 2 hours for deep work" | Compute gaps → filter by working hours + duration |
| `update_event` | "Move the team meeting to Friday" | Resolve event → apply changes → conflict check |
| `delete_event` | "Cancel the dentist appointment" | Resolve → delete → queue Google delete |
| `skip_occurrence` | "Skip this week's standup" | Find recurring event → create exception for that date |
| `create_reminder` | "Remind me to call John at 5pm" | Create standalone or event-linked reminder |
| `list_reminders` | "What reminders do I have?" | Query unsent reminders |
| `set_working_hours` | "My hours are 9am to 6pm" | Update user's working_hours_start/end |
| `search_events` | "When did I last meet with Sarah?" | Fuzzy title/tag search, past/future, count queries |
| `set_preference` | "Default events to 30 minutes" | Update user preferences JSONB |
| `daily_digest` | "What does my day look like?" | Events + stats (meeting hours, free time, busiest day) |
| `google_calendar` | "Connect my Google Calendar" | Route to OAuth flow / import / disconnect / status |
| `unknown` | Anything else | Helpful fallback with suggestions |

Follow-up resolution: responses include context tags (`[ctx:{...}]`) so the LLM can resolve "cancel that", "make it 4pm instead", "add a reminder for it" by extracting the event_id from conversation history.

## Key Design Decisions

- **Conversational first** — The chat interface IS the product. Every feature is accessible via natural language.
- **UTC storage** — All times stored as UTC in the DB, converted to user timezone for display.
- **LLM as structured extractor** — The LLM parses NL into JSON; business logic stays in Python.
- **HMAC on every request** — Every request from Maya is signature-verified with timestamp freshness.
- **Encrypted tokens at rest** — Google OAuth tokens encrypted with Fernet before DB storage.
- **Async push queue** — Google sync is decoupled; calendar ops return instantly, sync is background.
- **RRULE expansion** — Recurring events stored as RFC 5545 RRULE strings, expanded at query time via `dateutil.rrulestr`.
- **Template matching** — 20+ built-in templates (standup=15min, gym=1hr@7am, etc.) + user custom templates.
- **Idempotent provision** — Maya may call provision multiple times; always safe.

## What Maya Looks Like (for context)

Maya is built with:
- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS v4 — deployed at `app.agentmaya.io`
- **Backend:** Python, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL — deployed at `api.agentmaya.io`
- **Auth:** JWT (access + refresh tokens)
- **LLM:** LangChain + LangGraph with OpenAI/Anthropic

Maya's backend repo is at `C:\nav\Mindlr\maya\backend\` if you need to reference how things work there. Key files:
- `backend/app/services/agent_caller.py` — how Maya calls this agent (HMAC signing logic)
- `backend/app/services/routing.py` — how Maya decides to route to this agent
- `backend/app/api/chat.py` — the chat pipeline that calls agents
- `backend/app/api/sso.py` — SSO token generation and validation

## Deployment

Configured via `render.yaml`:
1. Deploy backend to Render — get a public URL
2. Register agent in Maya's admin panel with name, slug (`calendar`), API URL, keywords
3. Copy `client_id` and `client_secret` to this agent's env vars
4. Render runs: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Set up DNS: `calendar.agentmaya.io` -> Render
6. Frontend CSP must allow: `frame-ancestors https://app.agentmaya.io https://agentmaya.io`
