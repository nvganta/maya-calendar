# Maya Calendar Agent — Integration Guide

> How to connect this agent to the Maya orchestrator.

---

## Prerequisites

Before integrating, you need:
- Maya's backend running (locally at `http://localhost:8000` or deployed at `https://api.agentmaya.io`)
- Maya admin panel access (to register the agent)
- A PostgreSQL database for this agent (separate from Maya's DB)
- An LLM API key (OpenAI or Anthropic)

---

## Step 1: Register the Agent in Maya

Go to Maya's admin panel and create a new agent:

| Field | Value |
|-------|-------|
| **Name** | Calendar |
| **Slug** | `calendar` |
| **Description** | Manages your calendar — schedule events, check availability, set reminders, daily digest |
| **API URL** | `https://calendar.agentmaya.io` (or `http://localhost:8001` for dev) |
| **Keywords** | `calendar, schedule, meeting, appointment, event, remind, reminder, free, busy, availability, reschedule, cancel meeting, book, time slot, agenda, week, tomorrow, today` |

Maya will generate:
- **Client ID** — identifies this agent in HMAC headers
- **Client Secret** — used for HMAC signing (shown once, save immediately!)

---

## Step 2: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Database (this agent's own PostgreSQL database, NOT Maya's)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/maya_calendar

# Maya integration (from Step 1)
MAYA_CLIENT_ID=cal_abc123def456
MAYA_CLIENT_SECRET=sec_your_secret_here
MAYA_API_URL=http://localhost:8000          # or https://api.agentmaya.io

# LLM for intent parsing (choose one)
LLM_PROVIDER=anthropic                      # "openai" or "anthropic"
OPENAI_API_KEY=sk-...                       # if using openai
ANTHROPIC_API_KEY=sk-ant-...                # if using anthropic

# JWT for frontend sessions (generate a random key)
# python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=your_random_64_char_hex_string

# Google Calendar OAuth (optional — sync disabled if not set)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8001/api/google/callback

# Token encryption key for OAuth tokens at rest (optional)
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
TOKEN_ENCRYPTION_KEY=your_fernet_key
```

### Required vs Optional

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | Yes | Must be PostgreSQL (asyncpg driver) |
| `MAYA_CLIENT_ID` | Yes | From Maya admin panel |
| `MAYA_CLIENT_SECRET` | Yes | From Maya admin panel |
| `MAYA_API_URL` | Yes | Maya backend URL |
| `LLM_PROVIDER` | Yes | `"openai"` or `"anthropic"` |
| `OPENAI_API_KEY` | If openai | — |
| `ANTHROPIC_API_KEY` | If anthropic | — |
| `JWT_SECRET_KEY` | Yes | Random hex string for frontend JWT |
| `GOOGLE_CLIENT_ID` | No | Google sync disabled without it |
| `GOOGLE_CLIENT_SECRET` | No | Google sync disabled without it |
| `GOOGLE_REDIRECT_URI` | No | Defaults to localhost |
| `TOKEN_ENCRYPTION_KEY` | No | Tokens stored unencrypted without it |

---

## Step 3: Set Up the Database

```bash
# Install dependencies
pip install -r requirements.txt

# Run all migrations
alembic upgrade head
```

This creates 7 tables across 4 migrations:
1. `users`, `events`, `reminders` (initial schema + indexes)
2. `recurring_event_exceptions`, working hours columns on users
3. `category` column on events, `preferences` JSONB on users
4. `google_oauth_tokens`, `external_event_mappings`, `sync_queue_items`

---

## Step 4: Start the Agent

```bash
# Development
uvicorn app.main:app --reload --port 8001

# Production (Render handles this via render.yaml)
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Verify it's running:
```bash
curl http://localhost:8001/health
# {"status": "ok", "agent": "calendar"}
```

---

## Step 5: Test the Integration

### Test Provision (User Registration)

When a user clicks "Connect" on the Calendar agent in Maya's marketplace, Maya calls:

```bash
# Maya signs this request with HMAC-SHA256
curl -X POST http://localhost:8001/api/maya/provision \
  -H "Content-Type: application/json" \
  -H "X-Maya-Client-ID: cal_abc123def456" \
  -H "X-Maya-Signature: <hmac_signature>" \
  -H "X-Maya-Timestamp: $(date +%s)" \
  -d '{"maya_user_id": 1, "email": "nav@example.com", "name": "Nav"}'
```

Expected response:
```json
{
  "agent_user_id": "550e8400-e29b-41d4-a716-446655440000",
  "needs_setup": false
}
```

`needs_setup: false` because this agent doesn't require external account linking to start working. Users can immediately chat after connecting.

### Test Chat (Message Handling)

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -H "X-Maya-Client-ID: cal_abc123def456" \
  -H "X-Maya-Signature: <hmac_signature>" \
  -H "X-Maya-Timestamp: $(date +%s)" \
  -d '{
    "message": "Schedule a team meeting tomorrow at 3pm",
    "user": {"maya_user_id": 1, "email": "nav@example.com", "name": "Nav"},
    "conversation_history": [],
    "context": {"agent_user_id": "550e8400-..."}
  }'
```

Expected response:
```json
{
  "response": "Done! I've scheduled 💼 **Team meeting** for Wed Apr 2, 3:00 – 4:00 PM."
}
```

---

## How HMAC Signing Works

Maya signs every request to prevent unauthorized access. Here's the protocol:

```python
import hmac
import hashlib
import json
import time

# Maya's side (agent_caller.py)
timestamp = str(int(time.time()))
body = json.dumps(payload)
message = f"{timestamp}.{body}"
signature = hmac.new(
    client_secret.encode(),  # The agent's client_secret (known to both Maya and agent)
    message.encode(),
    hashlib.sha256
).hexdigest()

# Headers sent:
# X-Maya-Client-ID: <client_id>
# X-Maya-Signature: <signature>
# X-Maya-Timestamp: <timestamp>
```

```python
# Agent's side (security.py)
# 1. Check client_id matches MAYA_CLIENT_ID
# 2. Check timestamp is within 5 minutes
# 3. Recreate HMAC with MAYA_CLIENT_SECRET and compare
```

---

## SSO Flow (For Frontend Access)

When a user clicks "Open Calendar" in Maya's UI, the SSO flow kicks in:

```
1. Maya generates a short-lived SSO token for the user
2. Maya redirects to: calendar.agentmaya.io?sso_token=abc123
3. Calendar frontend sends token to: POST /api/sso/validate
4. Calendar backend calls Maya: POST {MAYA_API_URL}/api/sso/validate
   Body: {"token": "abc123", "client_id": "cal_...", "client_secret": "sec_..."}
5. Maya returns: {"user": {"id": 1, "email": "nav@example.com", "name": "Nav"}}
6. Calendar backend creates/finds local user, issues a JWT
7. Frontend stores JWT for subsequent API calls
```

---

## Google Calendar Setup (Optional)

To enable Google Calendar sync:

### 1. Create Google Cloud Project
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a new project (or use existing)
- Enable the **Google Calendar API**

### 2. Create OAuth 2.0 Credentials
- Go to APIs & Services → Credentials
- Create OAuth 2.0 Client ID (Web application)
- Add authorized redirect URI: `https://calendar.agentmaya.io/api/google/callback`
  (or `http://localhost:8001/api/google/callback` for dev)
- Copy Client ID and Client Secret

### 3. Configure Environment
```bash
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=https://calendar.agentmaya.io/api/google/callback
```

### 4. Generate Token Encryption Key
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Set `TOKEN_ENCRYPTION_KEY` to the output.

### 5. User Connects via Chat
Users can say "connect my Google Calendar" in Maya, and the agent will guide them through the OAuth flow.

---

## Deployment (Render)

The `render.yaml` file configures deployment:

```yaml
services:
  - type: web
    name: maya-calendar
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: maya-calendar-db
          property: connectionString
      # ... other env vars

databases:
  - name: maya-calendar-db
    plan: free
    databaseName: maya_calendar
```

### Deployment Checklist

- [ ] Set all required env vars in Render dashboard
- [ ] Verify database connection (Render provisions PostgreSQL)
- [ ] Migrations run automatically on deploy (in startCommand)
- [ ] Test health check: `curl https://calendar.agentmaya.io/health`
- [ ] Register agent in Maya's admin panel with the Render URL
- [ ] Test end-to-end: send a calendar message through Maya

### DNS Setup
- Point `calendar.agentmaya.io` to Render
- Ensure CORS allows Maya's frontend domain (already configured in `main.py`)
- Frontend CSP: `frame-ancestors https://app.agentmaya.io https://agentmaya.io`

---

## Troubleshooting

### "Invalid signature" (401)
- Check that `MAYA_CLIENT_ID` and `MAYA_CLIENT_SECRET` match what's in Maya's admin panel
- Check that the clock isn't more than 5 minutes off between Maya and this agent

### "User not found" (404)
- Ensure `/api/maya/provision` was called before `/chat`
- Or check that the `user` field is included in the chat request (auto-provision fallback)

### Intent parsing returns "unknown" for everything
- Check that `LLM_PROVIDER` is set to `"openai"` or `"anthropic"`
- Check that the corresponding API key is valid
- Check logs for LLM response errors

### Google sync not working
- Check that `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set
- Check logs for "Sync worker disabled" message (means Google isn't configured)
- Verify the OAuth redirect URI matches exactly what's in Google Cloud Console
