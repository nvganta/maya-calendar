# Maya Calendar Agent — API Reference

> All HTTP endpoints exposed by this agent.

---

## Maya Integration Endpoints

These are called by the Maya orchestrator, not by users directly. All require HMAC-SHA256 signature verification.

### POST `/api/maya/provision`

Called when a user connects this agent from Maya's marketplace.

**Headers:**
```
Content-Type: application/json
X-Maya-Client-ID: <client_id>
X-Maya-Signature: HMAC-SHA256("{timestamp}.{body}", MAYA_CLIENT_SECRET)
X-Maya-Timestamp: <unix_timestamp>
```

**Request Body:**
```json
{
  "maya_user_id": 1,
  "email": "user@example.com",
  "name": "User Name"
}
```

**Response (200):**
```json
{
  "agent_user_id": "550e8400-e29b-41d4-a716-446655440000",
  "needs_setup": false
}
```

**Behavior:**
- Idempotent — calling multiple times with the same `maya_user_id` returns the existing user
- Creates a new local User record if one doesn't exist
- `needs_setup` is always `false` (no external account linking required)

---

### POST `/chat`

Called every time Maya routes a calendar-related message to this agent.

**Headers:** Same HMAC headers as provision.

**Request Body:**
```json
{
  "message": "Schedule a meeting tomorrow at 3pm",
  "user": {
    "maya_user_id": 1,
    "email": "user@example.com",
    "name": "User Name"
  },
  "conversation_history": [
    {"role": "user", "content": "Schedule a meeting tomorrow at 3pm"},
    {"role": "assistant", "content": "Done! I've scheduled..."}
  ],
  "context": {
    "agent_user_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Response (200):**
```json
{
  "response": "Done! I've scheduled 💼 **Team meeting** for Wed Apr 2, 3:00 – 4:00 PM.\n[ctx:{\"event_id\":\"...\",\"title\":\"Team meeting\",\"time\":\"...\"}]"
}
```

**Behavior:**
- Parses intent via LLM → executes calendar action → returns natural language response
- User resolution: tries `context.agent_user_id` first, falls back to `user.maya_user_id`, auto-provisions if needed
- Response may contain a `[ctx:{...}]` tag at the end for follow-up resolution (hidden from user display)

---

## Google Calendar Endpoints

### GET `/api/google/auth-url`

Generate the Google OAuth consent screen URL.

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | UUID | Yes | The local user ID |

**Response (200):**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/auth?..."
}
```

---

### GET `/api/google/callback`

OAuth redirect callback. Google redirects here after user grants consent.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `code` | string | Authorization code from Google |
| `state` | string | Signed state token (CSRF protection) |

**Response (200):**
```json
{
  "status": "connected",
  "google_email": "user@gmail.com"
}
```

**Error (400):** Invalid or expired state token.

---

### POST `/api/google/disconnect`

Revoke Google token and remove from database.

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | UUID | Yes | The local user ID |

**Response (200):**
```json
{
  "status": "disconnected"
}
```

---

### GET `/api/google/status`

Check current Google connection status.

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | UUID | Yes | The local user ID |

**Response (200):**
```json
{
  "connected": true,
  "google_email": "user@gmail.com",
  "scopes": "https://www.googleapis.com/auth/calendar",
  "token_expires_at": "2026-04-01T15:30:00+00:00",
  "connected_at": "2026-03-15T10:00:00+00:00"
}
```

---

## SSO Endpoint

### POST `/api/sso/validate`

Validates a Maya SSO token and issues a local JWT for frontend sessions.

**Request Body:**
```json
{
  "token": "sso_abc123..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "550e8400-...",
    "email": "user@example.com",
    "name": "User Name"
  }
}
```

**Behavior:**
- Calls Maya's `POST /api/sso/validate` to verify the token
- Finds or creates a local user
- Returns a JWT valid for 24 hours

---

## Health Check

### GET `/health`

**Response (200):**
```json
{
  "status": "ok",
  "agent": "calendar"
}
```

---

## Event CRUD Endpoints (Frontend)

All endpoints require JWT authentication via the SSO flow (`Authorization: Bearer <token>`).

```
GET    /api/events                      # List events in date range (with RRULE expansion)
POST   /api/events                      # Create event
GET    /api/events/{id}                 # Get single event
PATCH  /api/events/{id}                 # Update event (partial)
DELETE /api/events/{id}                 # Delete event
GET    /api/events/reminders/pending    # List unsent reminders
POST   /api/events/reminders            # Create reminder
DELETE /api/events/reminders/{id}       # Delete reminder
GET    /api/user                        # Get user settings
PATCH  /api/user                        # Update user settings (timezone, working hours, preferences)
```

Events with `recurrence` are expanded via RRULE into virtual occurrences within the queried date range. Virtual occurrences receive deterministic `uuid5` IDs. Cancelled occurrences (via `RecurringEventException`) are excluded. All mutations queue Google Calendar sync when the user has Google connected.

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error description"
}
```

| Status | Meaning |
|--------|---------|
| 401 | Invalid client ID, invalid HMAC signature, or expired timestamp |
| 404 | User not found (and auto-provision failed) |
| 422 | Invalid request body (Pydantic validation error) |
| 500 | Internal server error |
