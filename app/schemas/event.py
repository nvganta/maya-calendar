import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, field_validator, model_validator


def _ensure_tz_aware(v: datetime) -> datetime:
    """Coerce naive datetimes to UTC. asyncpg requires tz-aware for TIMESTAMPTZ."""
    if v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


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

    @field_validator("start_time", "end_time", mode="after")
    @classmethod
    def tz_aware(cls, v: datetime) -> datetime:
        return _ensure_tz_aware(v)

    @model_validator(mode="after")
    def end_after_start(self):
        if not self.is_all_day and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


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

    @field_validator("start_time", "end_time", mode="after")
    @classmethod
    def tz_aware(cls, v: datetime | None) -> datetime | None:
        return _ensure_tz_aware(v) if v is not None else None

    @model_validator(mode="after")
    def end_after_start(self):
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be after start_time")
        return self


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

    @field_validator("remind_at", mode="after")
    @classmethod
    def tz_aware(cls, v: datetime) -> datetime:
        return _ensure_tz_aware(v)


class ReminderResponse(BaseModel):
    id: uuid.UUID
    message: str
    remind_at: datetime
    is_sent: bool
    event_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
