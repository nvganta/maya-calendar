# Maya Calendar Agent

An AI calendar assistant that lives inside the Maya ecosystem. You talk to Maya, and when the conversation is about scheduling, availability, reminders, or anything calendar-related, Maya routes it here.

Everything happens through natural conversation. "Schedule a meeting with the team Thursday at 3pm" creates an event. "Am I free tomorrow afternoon?" checks your availability. "Skip this week's standup" creates an exception on a recurring event. No forms, no calendar UI required.

## What it does

Full calendar management through chat: create, update, delete events, check availability, find free time slots, manage recurring events (RFC 5545 RRULE), set reminders, get daily/weekly digests with meeting statistics, and bidirectional Google Calendar sync.

See `docs/OVERVIEW.md` for the full capabilities list, or `docs/PHASES.md` for what's built and what's planned.

## Tech stack

| Layer | What |
|-------|------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL |
| AI | OpenAI (gpt-4o-mini) or Anthropic (claude-haiku) for intent parsing |
| Google Sync | google-api-python-client, OAuth 2.0, Fernet token encryption |
| Background | asyncio workers (reminders every 60s, sync every 60s/5min) |
| Deployment | Render.com |

## Quick start

```bash
# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Fill in DATABASE_URL, MAYA_CLIENT_ID, MAYA_CLIENT_SECRET, LLM keys

# Database
alembic upgrade head

# Run
uvicorn app.main:app --reload --port 8001
```

Port 8001. Maya runs on 8000, Calendar on 8001, Notes on 8002.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL (this agent's own DB) |
| `MAYA_CLIENT_ID` | Yes | From Maya admin panel |
| `MAYA_CLIENT_SECRET` | Yes | From Maya admin panel |
| `MAYA_API_URL` | Yes | Maya's backend URL |
| `LLM_PROVIDER` | Yes | `"openai"` or `"anthropic"` |
| `OPENAI_API_KEY` | If openai | For intent parsing |
| `ANTHROPIC_API_KEY` | If anthropic | For intent parsing |
| `JWT_SECRET_KEY` | Yes | For frontend SSO sessions |
| `GOOGLE_CLIENT_ID` | No | Google OAuth (sync disabled without it) |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth |
| `TOKEN_ENCRYPTION_KEY` | No | Fernet key for encrypting Google tokens at rest |

## Project structure

```
maya-calendar/
├── app/
│   ├── main.py           # FastAPI entry point + background workers
│   ├── core/             # Config, database, HMAC security, JWT auth
│   ├── models/           # 7 SQLAlchemy models (user, event, reminder, google tokens, sync queue)
│   ├── schemas/          # Pydantic DTOs for Maya and event endpoints
│   ├── api/              # Routes: Maya integration, events, Google OAuth, SSO
│   └── services/         # Intent parsing, calendar logic (1,300+ lines), Google sync, workers
├── tests/                # 1,000+ lines (CRUD, formatting, recurring, preferences, security)
├── alembic/              # 4 database migrations
├── docs/                 # Documentation
└── render.yaml           # Deployment config
```

## Documentation

- `CLAUDE.md` — Technical reference (what Claude reads every session)
- `docs/OVERVIEW.md` — Capabilities, quick start, key metrics
- `docs/ARCHITECTURE.md` — System diagrams, request lifecycle, database schema
- `docs/INTEGRATION.md` — Step-by-step guide to connect to Maya
- `docs/API.md` — All HTTP endpoints with examples
- `docs/PHASES.md` — Development roadmap and current status
- `docs/RESEARCH.md` — Competitive analysis of calendar apps

## Current status

Phases 1-3 complete (core calendar CRUD, recurring events, reminders, digests, preferences, search, templates). Phase 4 mostly complete (Google Calendar bidirectional sync with OAuth, encrypted tokens, async push queue). Phases 5-6 not started (collaboration, booking pages, analytics, frontend).

See `docs/PHASES.md` for the full breakdown.
