# Maya Calendar Agent — Super Calendar Research

> Compiled research on what it takes to build a best-in-class AI calendar agent.
> Sources: Reclaim.ai, Motion, Clockwise, Clara, Cal.com, Calendly, Fantastical, Vimcal, Amie, Google Calendar, Apple Calendar, Outlook, and broader UX research.

---

## Table of Contents

1. [Core Calendar Capabilities](#1-core-calendar-capabilities)
2. [AI-Powered Intelligence](#2-ai-powered-intelligence)
3. [Natural Language Understanding](#3-natural-language-understanding)
4. [Conflict Resolution & Smart Suggestions](#4-conflict-resolution--smart-suggestions)
5. [Productivity & Wellbeing Features](#5-productivity--wellbeing-features)
6. [Collaborative Scheduling](#6-collaborative-scheduling)
7. [Booking & Appointment Pages](#7-booking--appointment-pages)
8. [Analytics & Insights](#8-analytics--insights)
9. [Integrations & APIs](#9-integrations--apis)
10. [UX Patterns & Best Practices](#10-ux-patterns--best-practices)
11. [Common User Pain Points](#11-common-user-pain-points)
12. [Competitive Landscape](#12-competitive-landscape)

---

## 1. Core Calendar Capabilities

### Event Management (CRUD)
- Create, read, update, delete events
- Single-day, multi-day, and all-day events
- Recurring events (daily, weekly, biweekly, monthly, yearly, custom patterns like "first Monday of each month")
- Recurring event exception handling (modify/skip single occurrences)
- Event duplication/cloning
- Event templates (e.g., "1:1 meeting" pre-filled with duration, description)
- Event color coding and categorization/tagging
- Event attachments (files, links, documents)
- Rich text descriptions and notes
- Location support (physical address + virtual meeting link)
- RSVP/attendance status (accepted, declined, tentative)
- Tentative/hold events vs. confirmed events
- Private/public event visibility
- Soft-delete with 30-day recovery

### Time Zone Handling
- All times stored as UTC in the database
- Store original timezone (IANA format) alongside UTC
- Multi-timezone display (show 2+ timezones side by side)
- Per-event timezone setting ("3pm Tokyo time" even if user is in EST)
- Auto-detect timezone from device/frontend
- Travel-aware timezone (auto-adjust when user travels)
- DST-safe recurrence ("9am local time every day" handles clock changes)

### Notifications & Reminders
- Customizable reminders per event (5 min, 15 min, 1 hour, 1 day, etc.)
- Multiple reminders per event
- Event-type-aware defaults (all-day events → morning-of, meetings → 15 min before)
- Standalone reminders (not tied to events) — "remind me to call John at 5pm"
- Morning daily digest — "Here's your day" summary
- Weekly schedule summary
- Multi-channel: push, email, SMS, Slack, WhatsApp
- Snooze options: "remind me in 30 min," "remind me when I arrive at work"
- "Time to leave" notifications based on travel time

### Calendar Sync & Interop
- Google Calendar sync (bidirectional)
- Microsoft Outlook/365 sync (bidirectional)
- Apple Calendar via CalDAV
- ICS file import/export
- CalDAV protocol support for self-hosted solutions
- Webhook notifications for event changes
- Incremental sync (only fetch changes since last sync)

---

## 2. AI-Powered Intelligence

### Smart Scheduling
- Auto-schedule tasks into optimal open calendar slots (like Reclaim, Motion)
- AI picks time based on priorities, deadlines, energy levels
- Automatic rescheduling when conflicts arise
- Priority-based scheduling (high-priority tasks get prime time slots)
- Deadline-aware scheduling (work backward from due date)
- Duration estimation based on historical patterns
- Schedule optimization — rearrange your day for maximum productivity

### Smart Meeting Coordination
- Find mutual availability across multiple participants
- Smart time suggestions based on preferences (not just availability)
- "Schedule for me" — AI autonomously coordinates with attendees
- Meeting load balancing across the week (avoid meeting-heavy days)
- Round-robin assignment for team scheduling
- Collective availability for group scheduling
- Meeting cost estimation (attendees × estimated hourly rate × duration)

### Learning & Adaptation
- Learn user preferences over time (prefers morning meetings, likes focus after lunch)
- Adapt suggestions based on accept/decline patterns
- Learn meeting duration preferences per meeting type
- Learn which meetings user frequently reschedules
- Predictive scheduling ("you usually have a team sync on Mondays — should I schedule one?")
- Relationship tracking ("it's been 3 weeks since you last met with Sarah")

### Pre/Post Meeting Intelligence
- Pre-meeting briefs (AI summarizes context about attendees, previous meetings)
- Auto-create meeting notes documents
- Post-meeting action item extraction (from transcripts)
- Auto-populate follow-up events based on meeting outcomes
- Auto-send agenda before meetings

---

## 3. Natural Language Understanding

### Date/Time Parsing
| Type | Examples |
|------|----------|
| Absolute | "March 15th at 2pm", "01/20/2026 14:00" |
| Relative | "tomorrow", "next week", "in 3 days", "this Friday" |
| Vague/Fuzzy | "sometime next week", "late afternoon", "early morning" |
| Range | "between 2 and 4pm", "Monday through Wednesday" |
| Contextual | "after my dentist appointment", "before the team standup" |
| Colloquial | "end of day", "lunch time", "COB", "EOD" |
| Duration | "for an hour", "30-minute call", "a quick sync" |
| Recurrence | "every weekday", "weekly on Tuesdays", "biweekly" |

### Edge Cases to Handle
- "Next Thursday" — nearest upcoming Thursday, or the one after? (Use nearest)
- "The meeting at 3" — 3am or 3pm? (Business hours = PM)
- "In the morning" — default to 9am, "afternoon" → 1pm, "evening" → 6pm
- "This weekend" — Saturday and Sunday of the coming weekend
- "EOD" / "COB" — configurable defaults
- Always echo parsed date/time back before creating: "I'll schedule 'Team Meeting' for Thursday March 12 at 3:00 PM EST. Sound good?"

### Intent Classification
| Intent | Example | Action |
|--------|---------|--------|
| `create_event` | "Schedule a meeting Thursday at 3pm" | Parse and create event |
| `list_events` | "What's on my calendar this week?" | Query date range |
| `check_availability` | "Am I free tomorrow afternoon?" | Report gaps |
| `update_event` | "Move the team meeting to Friday" | Find and update |
| `delete_event` | "Cancel the dentist appointment" | Find and delete |
| `create_reminder` | "Remind me to call John at 5pm" | Create reminder |
| `list_reminders` | "What reminders do I have?" | Query reminders |
| `find_time` | "When can I meet with Sarah this week?" | Availability search |
| `create_focus_time` | "Block 2 hours for deep work tomorrow" | Create protected block |
| `daily_summary` | "What does my day look like?" | Today's agenda |
| `reschedule` | "Push my 3pm back an hour" | Contextual update |
| `compound` | "Cancel the 3pm and reschedule for tomorrow" | Multi-action |
| `preference` | "I prefer meetings in the afternoon" | Store preference |
| `analytics` | "How many meetings did I have this week?" | Generate report |
| `unknown` | Anything else | Helpful fallback |

### Entity Extraction
- Event title/subject
- Participants/attendees (by name or email)
- Location (physical or virtual)
- Date and time
- Duration
- Recurrence pattern
- Priority level
- Category (work, personal, health)
- Meeting type (1:1, team, external)

### Conversation Context
- Remember within conversation: "make it 4pm instead" (knows what "it" refers to)
- Handle pronouns: "move it", "cancel that", "make it longer"
- Multi-turn flows: "Schedule a meeting" → "With whom?" → "Sarah and John" → "How about Thursday at 2?"

### Recommended Libraries
| Library | Purpose |
|---------|---------|
| `dateparser` | Primary natural language date parsing (200+ languages) |
| `parsedatetime` | Fallback for relative dates |
| `python-dateutil` | RRULE for recurrence, structured date parsing |
| `icalendar` | Parse/generate .ics files |

---

## 4. Conflict Resolution & Smart Suggestions

### Conflict Detection
- Real-time overlap detection when creating/moving events
- Double-booking warnings
- Cross-calendar conflict detection (personal + work)
- Soft conflict warnings (back-to-back meetings with no buffer)
- Travel time conflicts (in-person meetings too close together geographically)

### Resolution Strategies
- Suggest alternative times when conflicts exist (ranked list)
- Auto-reschedule lower-priority events to make room
- "Flexible" events that auto-move when conflicts arise
- Priority-based resolution (higher priority wins the slot)
- Allow force double-book with explicit warning
- Smart event merging suggestions ("you have 3 short meetings with the same team — combine?")

### Proactive Suggestions
- "You have 5 meetings in a row — want me to add a break?"
- "You haven't scheduled focus time this week — want me to block some?"
- "This meeting could be 30 min instead of 60 based on the agenda"
- "You usually have 1:1s with Sarah on Tuesdays — want to schedule one?"
- "A meeting is splitting a 3-hour focus block into two unusable 30-min gaps — reschedule it?"

---

## 5. Productivity & Wellbeing Features

### Focus/Deep Work Time
- Auto-block focus time on calendar
- Protect focus time from meeting invites (mark as "busy")
- Configurable minimum focus block duration
- Focus time preferences (morning person vs. afternoon)
- DND/notification suppression during focus blocks
- Focus time goals ("I want 4 hours of focus time per day")
- Track achievement vs. goal

### Buffer Time
- Auto buffer before/after meetings (configurable per meeting type)
- Lunch break protection (never schedule over lunch)
- End-of-day buffer (stop scheduling after a certain time)
- Per-meeting-type rules (15 min after external, 5 min after internal)

### Travel Time
- Auto-calculate and block travel time between in-person meetings
- Different travel mode estimates (driving, transit, walking)
- Account for traffic/rush hour
- Dynamic adjustment based on surrounding event locations

### Working Hours & Availability
- Set working hours per day (different hours for different days)
- "Out of office" mode that auto-declines
- Meeting-free days ("No Meeting Wednesdays")
- Meeting-free windows ("No meetings before 10am")
- Maximum meeting hours per day/week caps

### Habits & Routines (Reclaim-style)
- Schedule recurring habits (exercise, reading, meditation)
- Habits are "flexible" — find open time but defend it
- Habit streaks and completion tracking
- Auto-reschedule habits around meetings
- Priority ordering (most important habits scheduled first)
- Time-of-day preferences

### Health & Wellbeing
- Meeting fatigue detection and warnings
- Break reminders
- Workload balance scoring
- Burnout risk indicators (too many meeting-heavy weeks in a row)
- Enforce maximum daily meeting hours
- Suggest walking meetings for short 1:1s

---

## 6. Collaborative Scheduling

### Group Availability
- View overlaid free/busy blocks for team members
- Multi-person availability API: "When are all these people free?"
- Visual overlay pattern (semi-transparent colored blocks per person)
- AI-optimized group time finding

### Meeting Polls
- Propose multiple time slots, participants vote
- No-account-required voting via link (critical for external participants)
- Auto-select the best time from votes
- Integrated with calendar (shows proposed times on your calendar)

### Shared Calendars
- Create shared calendars (family, team, project)
- Granular permissions: view free/busy only, view titles, view full details, edit
- Change attribution (who changed what)
- Instant propagation

### Team Features
- Team-wide focus time optimization
- Org-level meeting policies
- Manager tools to protect team's time
- Cross-team scheduling optimization

---

## 7. Booking & Appointment Pages

### Core Booking Features
- Public scheduling link (`calendar.agentmaya.io/username`)
- Availability rules (days, hours, slot duration, buffers)
- Multiple event types (15-min call, 30-min meeting, 60-min consultation)
- Buffer between bookings
- Daily/weekly booking limits
- Minimum scheduling notice (e.g., can't book less than 24 hours ahead)
- Booking confirmation with .ics attachment
- Cancellation/rescheduling via link (up to configurable cutoff)
- Custom branding

### Advanced Booking
- Round-robin booking (distribute across team members)
- Collective availability (meeting requires ALL team members free)
- Routing forms (pre-booking questions to route to right person)
- Conditional logic in booking flows
- Payment collection at booking time (via Stripe)
- Embeddable scheduling widget for websites

---

## 8. Analytics & Insights

### Time Audit
- Automatic time categorization (meetings, focus, personal, admin)
- Weekly/monthly time breakdown by category
- Meeting vs. focus time ratio
- Time spent per project or client (via tagging)
- Comparison to goals
- Trend analysis over weeks/months

### Meeting Analytics
- Total meeting hours per week/month
- Average meeting duration
- Meeting frequency with specific people
- 1:1 frequency tracking
- External vs. internal meeting split
- Acceptance/decline rates
- "Meetings that could have been emails" detection

### Productivity Metrics
- Fragmentation score (how broken up is your day)
- Longest uninterrupted focus block
- Context switching frequency
- Calendar density/utilization rate

### Team Analytics
- Team-wide meeting load
- Focus time across the team
- Meeting culture metrics
- Cost of meetings (attendees × hourly rate × duration)
- Team availability heatmap

---

## 9. Integrations & APIs

### Calendar Providers
| Provider | API | Auth | Key Feature |
|----------|-----|------|-------------|
| Google Calendar | REST v3 | OAuth 2.0 | Auto Meet links, FreeBusy, push notifications, incremental sync |
| Microsoft Outlook | Graph API | OAuth 2.0 (Azure AD) | `findMeetingTimes`, auto Teams links, delta queries |
| Apple Calendar | CalDAV | App-specific passwords | WebDAV/XML, no push (must poll) |
| Self-hosted | CalDAV | Various | Nextcloud, Radicale, Baikal, Fastmail |

### Video Conferencing
| Service | How to Generate Links |
|---------|----------------------|
| Google Meet | Via Google Calendar API (`conferenceData.createRequest`) |
| Microsoft Teams | Via Graph API (`isOnlineMeeting: true`) or standalone `/onlineMeetings` |
| Zoom | `POST /users/{userId}/meetings` → returns `join_url` |
| Webex | `POST /meetings` → returns `webLink` |

### Communication / Notifications
| Channel | Service | Key Capability |
|---------|---------|----------------|
| Slack | `slack-sdk` | `chat.postMessage`, `chat.scheduleMessage`, Block Kit for interactive buttons |
| Email | SendGrid, Resend, AWS SES | Transactional emails, .ics attachments, scheduled sends |
| SMS | Twilio | Scheduled messages via `SendAt`, two-way messaging |
| WhatsApp | Twilio or Meta Cloud API | Template-based reminders (requires pre-approval) |
| Push | Firebase (FCM), OneSignal | Mobile/web push with scheduling |

### Location & Travel
| API | Purpose |
|-----|---------|
| Google Maps Directions | Travel time with real-time traffic (driving, transit, walking) |
| Google Distance Matrix | Multi-origin/destination travel times in one call |
| Google Geocoding | Address ↔ lat/lng conversion |
| Google Places | Location autocomplete for event creation |
| Mapbox Directions | Alternative to Google, often cheaper at scale |

### Weather
| API | Best For |
|-----|----------|
| OpenWeatherMap | 5-day forecast, free tier (1000 calls/day) |
| WeatherAPI.com | 14-day forecast + sunrise/sunset data |
| Tomorrow.io | Hyper-local, minute-by-minute precipitation |
| Visual Crossing | Historical + forecast, good free tier |

### Task Management
| Tool | API Type | Use Case |
|------|----------|----------|
| Todoist | REST | Create tasks with due dates, bidirectional sync |
| Notion | REST | Sync with databases, auto-create meeting notes |
| Linear | GraphQL | Surface dev deadlines on calendar |
| Jira | REST | Sprint deadlines, issue tracking |
| Asana | REST | Task and project sync |
| GitHub | GraphQL | Milestone and PR deadlines |

### Payments
| Service | Use Case |
|---------|----------|
| Stripe Checkout | Paid appointments at booking time |
| Stripe Connect | Marketplace model (platform fee) |
| Square Appointments | In-person service businesses |

### Other Useful APIs
| API | Purpose |
|-----|---------|
| Nager.Date | Public holidays by country (free, no auth) |
| Google Time Zone | Timezone for a lat/lng coordinate |
| Google People / MS Contacts | Attendee autocomplete |
| Clearbit | Enrich email addresses with company/role info |
| Otter.ai / Fireflies.ai | Meeting transcription and summaries |

### Key Python Packages
| Package | Purpose |
|---------|---------|
| `dateparser` | Natural language date parsing |
| `python-dateutil` | RRULE recurrence + structured parsing |
| `icalendar` | Parse/generate .ics files |
| `caldav` | CalDAV protocol (Apple, Nextcloud, etc.) |
| `google-api-python-client` | Google Calendar, Meet, Maps |
| `msgraph-sdk` / `O365` | Microsoft Graph (Outlook, Teams) |
| `slack-sdk` | Slack notifications |
| `twilio` | SMS/WhatsApp |
| `stripe` | Payment processing |
| `httpx` | Async HTTP for APIs without SDKs |
| `pytz` / `zoneinfo` | Timezone conversions |

---

## 10. UX Patterns & Best Practices

### Calendar Views (for Frontend)
| View | Description | Priority |
|------|-------------|----------|
| Day | Vertical timeline, 24h | Must-have |
| Week | 7-column grid, vertical time axis | Must-have (most used) |
| Month | Traditional grid, events as pills | Must-have |
| Agenda/List | Chronological list of upcoming events | Must-have (great for mobile) |
| 3-Day | Compact mobile view | Nice-to-have |
| Year | Heat-map of busy vs. free days | Nice-to-have |
| Multi-person | Side-by-side columns per team member | V2 |

### Visual Design Essentials
- Color coding per calendar (work = blue, personal = green, etc.)
- Drag-and-drop rescheduling and resizing
- Click on any time slot for quick-add
- "Now" line on day/week view showing current time
- Weekend dimming for non-working days
- Event density indicators on month view

### Accessibility (Non-Negotiable)
- Screen reader support with proper ARIA labels
- Full keyboard navigation
- High contrast mode (WCAG AA 4.5:1 ratio)
- Text scaling to 200% zoom
- Color-blind friendly palettes (patterns + icons alongside color)
- Respect `prefers-reduced-motion`

### Inclusivity
- Multi-language date formatting
- Configurable first day of week (Sunday, Monday, Saturday)
- 12-hour vs. 24-hour time preference
- Date format preference (MM/DD vs. DD/MM vs. YYYY-MM-DD)
- Cultural/religious calendar overlays (Lunar, Islamic, Hebrew)
- Regional holiday support

### Privacy & Data Handling
- Free/busy sharing by default; detailed sharing is opt-in
- Granular permissions per calendar, per person
- Encrypted event data at rest (especially descriptions with links/passwords)
- GDPR compliance: export (.ics), delete, clear retention policies
- Audit logging for shared calendars
- Don't expose meeting links in public views

---

## 11. Common User Pain Points

### What People Hate About Current Calendars

**Scheduling friction:**
- "Too many clicks to create an event" → Need NL quick-add
- "Can't easily see when everyone is free" → Group availability view
- "Rescheduling is painful" → Drag-and-drop + NL ("move my 3pm to tomorrow")

**Notification problems:**
- "Too many / not enough reminders" → Per-event-type customization
- "All-day events remind me at midnight" → Smart defaults
- "No morning summary of my day" → Daily digest

**Timezone chaos:**
- "Wrong timezone on events" → Always confirm TZ, echo it back
- "Calendar goes haywire when traveling" → Location-aware TZ detection

**Missing intelligence:**
- "Why can't my calendar suggest when to schedule?" → AI scheduling
- "It doesn't learn my preferences" → Pattern learning
- "Can't handle 'move my 3pm to tomorrow'" → Context-aware NL

**Collaboration gaps:**
- "Can't share availability with non-users" → Public booking pages
- "Meeting polls require everyone on the same app" → Link-based, no-signup polls

---

## 12. Competitive Landscape

| Tool | Core Differentiator |
|------|-------------------|
| **Reclaim.ai** | Smart habits, flexible time defense, task auto-scheduling |
| **Motion** | AI auto-schedules entire day, project management + calendar |
| **Clockwise** | Team-level focus time optimization, org meeting culture |
| **Clara / x.ai** | Fully autonomous email-based scheduling (CC the AI) |
| **Cal.com** | Open-source scheduling infrastructure, API-first |
| **Calendly** | Polished booking pages, workflows, payment collection |
| **Google Calendar** | Auto-events from Gmail, Workspace integration, widest adoption |
| **Apple Calendar** | Siri NL, cross-device sync, travel time, privacy |
| **Vimcal** | Speed-focused UI, keyboard shortcuts, power users |
| **Amie** | Beautiful design, integrated tasks, scheduling links |
| **Fantastical** | Best natural language parsing, calendar sets, weather |

### Our Unique Position
Maya Calendar Agent is different because:
- It's conversational-first (accessed via chat with Maya, not a standalone app)
- It's part of a multi-agent ecosystem (can coordinate with other agents)
- It doesn't require a separate app — users interact through Maya
- It can be enhanced with other Maya agents (e.g., Finance agent for paid appointments, Email agent for meeting coordination)
