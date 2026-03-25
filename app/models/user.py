import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    maya_user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    # Working hours (hour of day, 0-23). Used for availability checks and free-slot suggestions.
    working_hours_start: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    working_hours_end: Mapped[int] = mapped_column(Integer, nullable=False, default=18)
    # User preferences JSON: default_duration_minutes, buffer_minutes, no_meeting_before,
    # preferred_meeting_start, preferred_meeting_end, default_reminder_minutes, custom_templates
    preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    events: Mapped[list["Event"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # noqa: F821
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # noqa: F821
