# Maya Calendar Agent

This is the Calendar Agent for Maya — an AI assistant hub where users talk to a central assistant (Maya) and Maya routes requests to specialized agents. This agent handles everything calendar-related: scheduling events, checking availability, setting reminders, and managing the user's schedule.

Users never call this agent directly. Maya forwards messages here when it detects calendar-related intent.

---

## How This Agent Fits Into Maya

Maya is the hub. This agent is a spoke. Here's the flow:

1. User sends a message to Maya: "Schedule a meeting with the team on Thursday at 3pm"
2. Maya detects calendar intent (via keywords or LLM classification)
3. Maya forwards the message to this agent's `/chat` endpoint with user context
4. This agent processes it (creates the event, checks conflicts, etc.)
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
Maya signs requests using this agent's `client_id` as the HMAC key. To verify:
```python
message = f"{timestamp}.{body}"
expected = hmac.new(client_id.encode(), message.encode(), hashlib.sha256).hexdigest()
hmac.compare_digest(signature, expected)
```
Reject if timestamp is older than 5 minutes.

**Response:**
```json
{
  "agent_user_id": "internal-user-id",
  "needs_setup": false
}
```

`needs_setup` is `false` because this agent doesn't require external account linking (unlike the Finance Agent which needs Plaid). Users can start using it immediately after connecting.

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
    "agent_user_id": "internal-user-id"
  }
}
```

**Response:**
```json
{
  "response": "You're free Thursday afternoon! Want me to schedule something?"
}
```

That's it. Just a response string. Maya handles streaming it to the user.

### 3. SSO (for the frontend)

When a user clicks "Open Calendar" in Maya:
1. Maya generates a short-lived token and redirects to this agent's frontend with `?sso_token=...`
2. The frontend sends the token to this agent's backend
3. This backend calls Maya's `POST /api/sso/validate` with the token + `client_id` + `client_secret`
4. Maya returns user info if valid
5. This agent logs the user in

**Validation request to Maya:**
```json
{
  "token": "<sso_token>",
  "client_id": "<MAYA_CLIENT_ID>",
  "client_secret": "<MAYA_CLIENT_SECRET>"
}
```

**Maya's SSO endpoint:** `POST {MAYA_API_URL}/api/sso/validate`

---

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic
- **LLM:** OpenAI or Anthropic for intent parsing and natural language understanding
- **Deployment target:** Render or Vercel (Python runtime)
- **Frontend (future):** Next.js at `calendar.agentmaya.io` (accessed via SSO from Maya)

## Project Structure

```
maya-calendar/
├── CLAUDE.md              # You are here
├── requirements.txt       # Python dependencies
├── .env.example           # Required environment variables
├── .gitignore
├── alembic.ini            # Alembic config
├── alembic/               # Database migrations
│   ├── env.py
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py      # Pydantic BaseSettings
│   │   ├── database.py    # Async SQLAlchemy engine + session
│   │   └── security.py    # HMAC verification helper
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py        # User model (linked to Maya via maya_user_id)
│   │   ├── event.py       # Calendar event model
│   │   └── reminder.py    # Reminder model (linked to events)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── maya.py        # Maya integration DTOs (provision, chat)
│   │   └── event.py       # Event/reminder request/response schemas
│   ├── api/
│   │   ├── __init__.py
│   │   ├── maya.py        # POST /api/maya/provision + POST /chat
│   │   └── events.py      # Direct CRUD for frontend (future)
│   └── services/
│       ├── __init__.py
│       ├── intent.py      # LLM-based intent parsing
│       └── calendar.py    # Calendar business logic (CRUD, conflict detection, etc.)
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
```

Port 8001 to avoid conflict with Maya's backend on 8000.

## Environment Variables

See `.env.example`. Key vars:
- `DATABASE_URL` — PostgreSQL connection string (this agent's own DB, not Maya's)
- `MAYA_CLIENT_ID` — from Maya admin panel when registering this agent
- `MAYA_CLIENT_SECRET` — from Maya admin panel (shown once, save immediately)
- `MAYA_API_URL` — Maya's backend URL (e.g., `https://api.agentmaya.io` or `http://localhost:8000` for dev)
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` — for intent parsing
- `LLM_PROVIDER` — "openai" or "anthropic"

## Data Model

### User
- `id` (UUID, PK)
- `maya_user_id` (int, unique) — links to the user in Maya's system
- `email` (string)
- `name` (string)
- `created_at`, `updated_at`

### Event
- `id` (UUID, PK)
- `user_id` (FK -> User)
- `title` (string)
- `description` (text, optional)
- `start_time` (datetime with timezone)
- `end_time` (datetime with timezone)
- `location` (string, optional)
- `is_all_day` (bool, default false)
- `recurrence` (string, optional — e.g., "daily", "weekly", "monthly")
- `tags` (array of strings, optional)
- `created_at`, `updated_at`

### Reminder
- `id` (UUID, PK)
- `event_id` (FK -> Event, optional — can be standalone)
- `user_id` (FK -> User)
- `message` (text)
- `remind_at` (datetime with timezone)
- `is_sent` (bool, default false)
- `created_at`

## Intent Parsing

The chat endpoint receives natural language. An LLM classifies the user's intent into one of:

| Intent | Example | Action |
|--------|---------|--------|
| `create_event` | "Schedule a meeting Thursday at 3pm" | Parse title, date, time, duration -> create event |
| `list_events` | "What's on my calendar this week?" | Query events for date range -> return list |
| `check_availability` | "Am I free tomorrow afternoon?" | Query events for time range -> report gaps |
| `update_event` | "Move the team meeting to Friday" | Find event, update fields |
| `delete_event` | "Cancel the dentist appointment" | Find event, delete it |
| `create_reminder` | "Remind me to call John at 5pm" | Create standalone reminder |
| `list_reminders` | "What reminders do I have?" | Query pending reminders |
| `unknown` | Anything else | Return helpful fallback message |

The LLM also extracts structured data: title, date/time, duration, location, etc.

## Key Design Decisions

- **No external calendar sync yet** — V1 is a standalone calendar. Google Calendar / Outlook sync is a future feature, which is why `needs_setup` is `false` on provision.
- **Timezone handling** — All times stored as UTC in the DB. User's timezone should be detected from the frontend or asked during first interaction.
- **Conflict detection** — When creating events, check for overlapping time ranges and warn the user.
- **Natural date parsing** — Use `dateparser` or similar library to handle "next Thursday", "tomorrow at 3", "in 2 hours", etc.
- **Conversation context** — Maya sends conversation_history, so the agent can handle follow-ups like "make it 4pm instead" after creating an event.

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

When ready to deploy:
1. Deploy backend to Render (or similar) — get a public URL
2. Register agent in Maya's admin panel with name, slug (`calendar`), API URL, keywords
3. Copy `client_id` and `client_secret` to this agent's env vars
4. Set up DNS: `calendar.agentmaya.io` -> hosting provider
5. Frontend CSP must allow: `frame-ancestors https://app.agentmaya.io https://agentmaya.io`
