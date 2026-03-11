from fastapi import APIRouter

router = APIRouter()


# Future: Direct CRUD endpoints for the calendar frontend (calendar.agentmaya.io)
# These will be used when we build the frontend UI.
# For now, all interaction goes through Maya's chat -> /chat endpoint.
#
# Planned endpoints:
# GET    /api/events          — list events for a date range
# POST   /api/events          — create event
# PATCH  /api/events/{id}     — update event
# DELETE /api/events/{id}     — delete event
# GET    /api/reminders       — list reminders
# POST   /api/reminders       — create reminder
# DELETE /api/reminders/{id}  — delete reminder
