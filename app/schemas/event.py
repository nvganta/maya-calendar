import uuid
from datetime import datetime
from pydantic import BaseModel


# --- Events ---

class EventCreate(BaseModel):
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime
    location: str | None = None
    is_all_day: bool = False
    recurrence: str | None = None
    tags: list[str] | None = None
    category: str | None = None


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = None
    is_all_day: bool | None = None
    recurrence: str | None = None
    tags: list[str] | None = None
    category: str | None = None


class EventResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    start_time: datetime
    end_time: datetime
    location: str | None
    is_all_day: bool
    recurrence: str | None
    tags: list[str] | None
    category: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- User Settings ---


class UserSettingsResponse(BaseModel):
    timezone: str | None
    working_hours_start: int
    working_hours_end: int
    preferences: dict | None

    model_config = {"from_attributes": True}


class UserSettingsUpdate(BaseModel):
    timezone: str | None = None
    working_hours_start: int | None = None
    working_hours_end: int | None = None
    preferences: dict | None = None


# --- Reminders ---

class ReminderCreate(BaseModel):
    message: str
    remind_at: datetime
    event_id: uuid.UUID | None = None


class ReminderResponse(BaseModel):
    id: uuid.UUID
    message: str
    remind_at: datetime
    is_sent: bool
    event_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
