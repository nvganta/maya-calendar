# Maya Calendar Agent — Implementation Phases

> What we're building and in what order.
> Each phase is deployable — users get value at the end of every phase.

---

## What We ARE Building

A conversational AI calendar agent that lives inside Maya. Users talk to Maya, Maya routes calendar-related messages here, we process and respond. No separate app needed.

## What We're NOT Building (at least not now)

- ❌ A standalone calendar app (we're a spoke agent, not a product)
- ❌ A Calendly/Cal.com clone (booking pages are Phase 5+)
- ❌ Full Google/Outlook sync (Phase 4+ — V1 is standalone)
- ❌ Team/org features (this is single-user first)
- ❌ A frontend (Phase 5+ — the chat IS the interface)

---

## Current Status (What Already Exists)

- ✅ FastAPI app with health check and CORS
- ✅ `/api/maya/provision` — user registration with HMAC verification
- ✅ `/chat` — receives messages, routes to intent parser
- ✅ HMAC signature verification matching Maya's signing logic
- ✅ Database models: User, Event, Reminder
- ✅ LLM intent parser (OpenAI or Anthropic) — classifies 7 intents
- ✅ Calendar service with CRUD, conflict detection, fuzzy event search
- ⚠️ No migrations generated yet
- ⚠️ Timezone stored but not used in parsing
- ⚠️ dateparser in requirements but not integrated
- ⚠️ Recurrence stored but not expanded for queries
- ⚠️ Reminders created but no delivery system
- ⚠️ No tests

---

## Phase 1: Solid Foundation
**Goal:** Make the existing code actually work end-to-end, tested, and deployable.

### 1A: Database & Migrations
- [ ] Generate initial Alembic migration from existing models
- [ ] Verify models create correctly (User, Event, Reminder)
- [ ] Add indexes (user_id + start_time on events, user_id + remind_at on reminders)
- [ ] Test migration up/down

### 1B: Fix the Core Chat Loop
- [ ] Integrate `dateparser` into intent parsing (replace raw string dates with actual datetime objects)
- [ ] Handle relative dates: "tomorrow", "next Thursday", "in 2 hours"
- [ ] Handle vague times: "morning" → 9am, "afternoon" → 1pm, "evening" → 6pm
- [ ] Default event duration: 1 hour if not specified
- [ ] Always echo parsed date/time back to user for confirmation
- [ ] Handle timezone: store user's timezone preference, use it in all parsing/display

### 1C: Improve Response Quality
- [ ] Better natural language responses (not robotic confirmations)
- [ ] Format event lists nicely (date, time, title, duration)
- [ ] Handle "no events found" gracefully
- [ ] Handle "I don't understand" gracefully with helpful suggestions
- [ ] Include conflict warnings in create_event responses

### 1D: Conversation Context
- [ ] Use `conversation_history` from Maya to handle follow-ups
- [ ] "Make it 4pm instead" — understand "it" refers to the last discussed event
- [ ] "Cancel that" — know what "that" means
- [ ] "Add a reminder for it" — link to the event being discussed

### 1E: Testing
- [ ] Unit tests for date parsing
- [ ] Unit tests for conflict detection
- [ ] Integration tests for chat endpoint (mock LLM)
- [ ] Integration tests for provision endpoint
- [ ] Test HMAC verification with known good/bad signatures

### 1F: Deployment Setup
- [ ] Dockerfile
- [ ] Environment variable validation on startup
- [ ] Health check endpoint (already exists, verify it)
- [ ] Deploy to Render (or similar)
- [ ] Register agent in Maya's admin panel
- [ ] End-to-end test: talk to Maya → get calendar response

**Phase 1 delivers:** A working calendar agent that Maya users can talk to. They can create events, list their schedule, check availability, and manage basic events through natural conversation.

---

## Phase 2: Smart Calendar
**Goal:** Go from "works" to "actually useful" — the features that make users rely on it daily.

### 2A: Recurring Events (Proper)
- [ ] Parse recurrence from NL: "every Monday at 10am", "daily standup at 9am", "biweekly 1:1"
- [ ] Store as RRULE (RFC 5545 compatible)
- [ ] Expand recurrences when listing events for a date range
- [ ] Handle "skip this week's standup" (single occurrence exceptions)
- [ ] Handle "change all future standups to 10:30am"
- [ ] Use `python-dateutil` rrule module for expansion

### 2B: Reminder System
- [ ] Background task (async worker or cron) to check for due reminders
- [ ] Deliver reminders through Maya's chat (call Maya's API to send a message to user)
  - OR: store pending reminders and deliver when user next interacts
- [ ] Standalone reminders: "remind me to buy groceries at 5pm"
- [ ] Event-linked reminders: "remind me 30 minutes before the meeting"
- [ ] Default reminders per event type (meetings → 15 min, all-day → morning of)
- [ ] "What reminders do I have?" — list pending reminders

### 2C: Daily Digest
- [ ] "What does my day look like?" — today's full agenda, formatted nicely
- [ ] "What about tomorrow?" — tomorrow's agenda
- [ ] "This week?" — week overview with busiest/freest days highlighted
- [ ] Proactive morning digest (if Maya supports scheduled agent messages)

### 2D: Smarter Updates & Deletes
- [ ] Fuzzy matching when user says "cancel the dentist appointment" (already partial)
- [ ] Handle ambiguity: "Which meeting did you mean? 1) Team Sync at 2pm 2) Design Review at 4pm"
- [ ] Bulk operations: "clear my Friday afternoon"
- [ ] "Move all my Thursday meetings to Friday" — batch reschedule

### 2E: Availability Intelligence
- [ ] "When am I free this week?" — list all open slots during working hours
- [ ] "Find me 2 hours for deep work tomorrow" — find the best contiguous block
- [ ] "Am I free between 2-4pm on Thursday?" — precise range check
- [ ] Consider working hours when reporting availability (don't suggest 3am)
- [ ] Working hours stored in user preferences

**Phase 2 delivers:** A calendar agent that handles real-world complexity — recurring meetings, reminders that actually fire, daily briefings, and smart availability checks. This is where users start depending on it.

---

## Phase 3: Productivity & Intelligence
**Goal:** The AI features that make this better than a regular calendar.

### 3A: Focus Time & Working Hours
- [ ] "Block focus time tomorrow morning" → create a protected block
- [ ] Let users set working hours: "My working hours are 9am to 6pm"
- [ ] Respect working hours in all suggestions and availability checks
- [ ] "Protect my lunch from 12-1pm every day" → recurring protected block
- [ ] Event categories: work, personal, focus, health
- [ ] No-meeting windows: "No meetings before 10am"

### 3B: Conflict Resolution (Advanced)
- [ ] When creating an event that conflicts: suggest 3 alternative times
- [ ] Consider buffer time in conflict detection (back-to-back warning)
- [ ] Priority-based conflicts: "This overlaps with 'Team Standup'. Should I move it, or schedule anyway?"
- [ ] Smart suggestions: "You have 5 meetings in a row — want me to add a 15-min break?"

### 3C: User Preferences & Learning
- [ ] Store preferences: preferred meeting times, default duration, buffer preferences
- [ ] NL preference setting: "I prefer meetings in the afternoon"
- [ ] Apply preferences when suggesting times
- [ ] Remember and apply: default event duration, default reminder timing, preferred days for certain activities

### 3D: Event Templates
- [ ] "Schedule a 1:1" → knows it's 30 min, recurring weekly, needs one other person
- [ ] "Schedule a team standup" → 15 min, daily, recurring
- [ ] Users can create templates: "When I say 'gym', create a 1-hour event called 'Gym' at 7am"
- [ ] Templates stored per user

### 3E: Natural Language Search
- [ ] "When did I last meet with Sarah?" — search by attendee
- [ ] "What meetings do I have about Project X?" — search by title/description/tags
- [ ] "How many meetings did I have last week?" — count queries
- [ ] "What's my next event?" — simple next-up query

**Phase 3 delivers:** An intelligent assistant that knows your preferences, protects your time, and proactively helps you manage your schedule better.

---

## Phase 4: External Integrations
**Goal:** Connect to the real world — sync with existing calendars, generate meeting links, multi-channel reminders.

### 4A: Google Calendar Sync
- [ ] OAuth 2.0 flow (user connects Google account via frontend/SSO)
- [ ] Bidirectional sync: events created here appear in Google, and vice versa
- [ ] Incremental sync using Google's `syncToken`
- [ ] Webhook for real-time updates from Google
- [ ] Conflict detection across both calendars
- [ ] Handle: "Import my Google Calendar events"

### 4B: Microsoft Outlook Sync
- [ ] OAuth 2.0 via Azure AD
- [ ] Bidirectional sync via Microsoft Graph
- [ ] Delta queries for incremental sync
- [ ] Use `findMeetingTimes` for smart group scheduling

### 4C: Video Meeting Links
- [ ] Auto-generate Zoom links when creating meetings (Zoom OAuth)
- [ ] Auto-generate Google Meet links (via Google Calendar API)
- [ ] Auto-generate Teams links (via Microsoft Graph)
- [ ] User preference: "Always add Zoom to my meetings"
- [ ] NL: "Schedule a Zoom call with Sarah at 3pm"

### 4D: Notification Channels
- [ ] Email reminders via SendGrid/Resend (with .ics attachment)
- [ ] Slack notifications (`slack-sdk` — message user when reminder is due)
- [ ] SMS reminders via Twilio (opt-in)
- [ ] User preference for notification channel

### 4E: Location & Travel Intelligence
- [ ] Google Maps integration for travel time between in-person events
- [ ] "You need to leave by 2:30pm to make your 3pm across town"
- [ ] Auto-block travel time on calendar
- [ ] Warn when back-to-back events at different locations aren't feasible

**Phase 4 delivers:** A connected calendar that syncs with Google/Outlook, auto-generates meeting links, and sends reminders through the user's preferred channels.

---

## Phase 5: Collaboration & Booking
**Goal:** Multi-user features and public scheduling.

### 5A: Multi-User Availability
- [ ] "When are me and Sarah both free this week?" (both must be Maya users)
- [ ] Group availability for 3+ people
- [ ] Suggest optimal meeting times for groups
- [ ] "Schedule a team meeting with Alice, Bob, and Charlie"

### 5B: Meeting Polls
- [ ] "Create a poll for the team dinner next week" → generate shareable link
- [ ] Propose 3-5 time slots, participants vote
- [ ] No account needed for voters (link-based)
- [ ] Auto-create event when voting closes

### 5C: Booking Pages (Calendly-like)
- [ ] Public scheduling link for each user
- [ ] Configurable availability rules and event types
- [ ] Buffer between bookings, daily limits, minimum notice
- [ ] Confirmation emails with .ics files
- [ ] Cancellation/rescheduling links

### 5D: Shared Calendars
- [ ] Create shared calendars (team, family, project)
- [ ] Permissions: view-only, edit, manage
- [ ] Shared calendar events visible in personal schedule

**Phase 5 delivers:** Collaboration features — group scheduling, polls, and public booking pages.

---

## Phase 6: Analytics & Frontend
**Goal:** Insights about how users spend their time, and a visual calendar interface.

### 6A: Calendar Analytics
- [ ] Time breakdown by category (meetings, focus, personal)
- [ ] Meeting hours per week/month with trend lines
- [ ] Focus time achieved vs. goal
- [ ] Fragmentation score (how broken up is your day)
- [ ] "How did I spend my time last week?" via chat

### 6B: Frontend (Next.js)
- [ ] SSO login flow (token from Maya → validate → session)
- [ ] Day / Week / Month / Agenda views
- [ ] Quick-add event modal
- [ ] Drag-and-drop rescheduling
- [ ] Color-coded calendars
- [ ] Mobile-responsive design

### 6C: Weather Integration
- [ ] Show weather forecast for outdoor events
- [ ] "Your outdoor team lunch on Thursday — 80% chance of rain"
- [ ] Weather data via OpenWeatherMap (free tier)

### 6D: Smart Features
- [ ] Holiday awareness (Nager.Date API — auto-block holidays)
- [ ] Habit tracking ("Did you complete your morning run?")
- [ ] Relationship tracking ("It's been 3 weeks since you met with Sarah")
- [ ] Event suggestions based on patterns

**Phase 6 delivers:** A full-featured calendar with visual interface, analytics, and smart quality-of-life features.

---

## Phase Summary

| Phase | Name | Core Deliverable | Key Intents |
|-------|------|------------------|-------------|
| **1** | Solid Foundation | Working agent end-to-end with Maya | create, list, check, update, delete |
| **2** | Smart Calendar | Recurring events, reminders, daily digest | + recurrence, reminders, digest |
| **3** | Productivity & Intelligence | Focus time, preferences, smart conflicts | + focus, search, templates |
| **4** | External Integrations | Google/Outlook sync, Zoom, notifications | + sync, meeting links |
| **5** | Collaboration & Booking | Group scheduling, polls, booking pages | + group, polls, booking |
| **6** | Analytics & Frontend | Visual calendar, insights, weather | + analytics, frontend |

---

## Technical Principles (All Phases)

1. **Conversational first** — The chat interface IS the product. Every feature should be accessible via natural language.
2. **Echo before acting** — Always confirm parsed details before creating/modifying events.
3. **Graceful degradation** — If the LLM misunderstands, ask a clarifying question instead of guessing.
4. **UTC storage** — All times in UTC in the DB, convert to user timezone for display.
5. **Idempotent provision** — Maya may call provision multiple times; handle gracefully.
6. **Test everything** — Each phase includes tests for its new features.
7. **Deploy continuously** — Each sub-phase (1A, 1B, etc.) should be deployable independently.
