# Maya Calendar Agent — Overview

> A conversational AI calendar assistant that lives inside Agent Maya.

---

## What Is This?

The Maya Calendar Agent is a **spoke agent** in the Agent Maya multi-agent system. It handles everything calendar-related — scheduling events, checking availability, setting reminders, managing recurring meetings, syncing with Google Calendar, and giving users daily/weekly digests — all through natural conversation.

Users never talk to this agent directly. They talk to **Maya** (the central orchestrator), and Maya routes calendar-related messages here.

### The User Experience

```
User:  "Schedule a team standup every Monday at 10am"
Maya:  [detects calendar intent, forwards to this agent]
Agent: [parses intent via LLM, creates recurring event with RRULE, detects conflicts]
Maya:  "Done! I've scheduled 💼 Team standup for Mon, 10:00 – 10:15 AM (repeats weekly on Mondays)."
```

```
User:  "What does my week look like?"
Maya:  [routes to calendar agent]
Agent: [queries events, computes stats, finds busiest/lightest days]
Maya:  "Here's your week — 12 events across 4 days:
        Monday — 3 events, 2h 30m ← busiest
        Tuesday — 2 events, 1h 30m
        Wednesday — free 🎉
        ..."
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+, FastAPI (async) |
| **Database** | PostgreSQL via SQLAlchemy 2.0 (async) + Alembic migrations |
| **LLM** | OpenAI (gpt-4o-mini) or Anthropic (claude-haiku) for intent parsing |
| **Google Sync** | google-api-python-client, google-auth-oauthlib (OAuth 2.0) |
| **Background** | asyncio tasks (reminder worker, sync worker) |
| **Deployment** | Render.com (Python runtime) |

---

## What It Can Do (Current Capabilities)

### Core Calendar (Phase 1)
- Create, update, delete events via natural language
- Conflict detection with alternative time suggestions
- Date/time parsing: "tomorrow at 3pm", "next Thursday morning", "in 2 hours"
- Conversation follow-ups: "cancel that", "make it 4pm instead", "add a reminder for it"

### Smart Calendar (Phase 2)
- **Recurring events** — RRULE (RFC 5545) with full expansion: "every Monday at 10am", "biweekly 1:1"
- **Skip occurrences** — "skip this week's standup" without cancelling the series
- **Reminders** — standalone ("remind me to call John at 5pm") or event-linked ("15 min before")
- **Background reminder delivery** — checks every 60s, pushes to Maya's notification API
- **Daily/weekly digest** — "what does my day look like?" with stats (meeting hours, free time, busiest days)
- **Availability** — "when am I free tomorrow?", "find me 2 hours for deep work"
- **Working hours** — "my working hours are 9am to 6pm" (respected in all suggestions)

### Productivity & Intelligence (Phase 3)
- **Event categories** — work, personal, focus, health (with icons: 💼 🏠 🎯 💪)
- **Event templates** — "standup" = 15 min, "gym" = 1hr at 7am, "1:1" = 30 min, "focus time" = 2hr
- **Custom templates** — "when I say gym, create a 1-hour health event at 7am"
- **User preferences** — default duration, buffer between meetings, no-meetings-before, preferred times
- **Natural language search** — "when did I last meet with Sarah?", "how many meetings last week?"
- **Back-to-back warnings** — "heads up, this is back-to-back with Team Sync"
- **Alternative slot suggestions** when conflicts arise

### Google Calendar Sync (Phase 4)
- **OAuth 2.0** with CSRF protection (signed state tokens) and encrypted tokens at rest (Fernet)
- **Bidirectional sync** — events created here appear in Google and vice versa
- **Async push queue** — local changes queued and pushed to Google in background
- **Incremental pull** — uses Google's syncToken for efficient delta sync (every 5 min)
- **Connect/disconnect/status** via chat: "connect my Google Calendar", "is my Google Calendar connected?"

---

## Project Structure

```
maya-calendar/
├── docs/                  # You are here
│   ├── OVERVIEW.md        # This file
│   ├── PHASES.md          # Development roadmap (6 phases)
│   ├── ARCHITECTURE.md    # Technical deep-dive
│   ├── INTEGRATION.md     # How to connect this agent to Maya
│   └── API.md             # API endpoint reference
├── app/
│   ├── main.py            # FastAPI entry point + lifespan (background workers)
│   ├── core/
│   │   ├── config.py      # Pydantic Settings (env vars)
│   │   ├── database.py    # Async SQLAlchemy engine + sessions
│   │   ├── security.py    # HMAC-SHA256 signature verification
│   │   └── auth.py        # JWT for frontend sessions (SSO)
│   ├── models/
│   │   ├── user.py        # User (linked to Maya via maya_user_id)
│   │   ├── event.py       # Calendar event (with RRULE, tags, category)
│   │   ├── reminder.py    # Reminders (event-linked or standalone)
│   │   ├── google_oauth_token.py   # Encrypted Google OAuth tokens
│   │   ├── recurring_exception.py  # Skip/reschedule individual occurrences
│   │   ├── external_event_mapping.py  # Local ↔ Google event ID mapping
│   │   └── sync_queue_item.py     # Async push queue for Google sync
│   ├── schemas/
│   │   ├── maya.py        # Maya integration DTOs (provision, chat)
│   │   └── event.py       # Event/reminder request/response schemas
│   ├── api/
│   │   ├── maya.py        # POST /api/maya/provision + POST /chat
│   │   ├── events.py      # Direct CRUD endpoints (future frontend)
│   │   ├── google.py      # Google OAuth flow endpoints
│   │   └── sso.py         # SSO validation for frontend sessions
│   └── services/
│       ├── intent.py      # LLM-based intent parser (14+ intents)
│       ├── calendar.py    # Calendar business logic (1,300+ lines)
│       ├── google_auth.py # Google OAuth 2.0 service
│       ├── google_sync.py # Bidirectional Google Calendar sync
│       ├── reminder_worker.py  # Background reminder checker
│       └── sync_worker.py     # Background Google sync (push + pull)
├── alembic/               # Database migrations (4 versions)
├── tests/                 # Test suite (1,000+ lines)
├── requirements.txt       # Python dependencies
├── render.yaml            # Render.com deployment config
└── CLAUDE.md              # AI assistant context file
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables (see docs/INTEGRATION.md for details)
cp .env.example .env
# Edit .env with your values

# 3. Run database migrations
alembic upgrade head

# 4. Start the server
uvicorn app.main:app --reload --port 8001
```

Port **8001** to avoid conflict with Maya's backend on 8000.

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Total source lines | ~5,900 |
| Core service (calendar.py) | ~1,310 lines |
| Intent types parsed | 14+ |
| Event templates (built-in) | 20+ |
| Database models | 7 |
| Alembic migrations | 4 |
| Test lines | ~1,000 |
| Background workers | 2 (reminders + sync) |
