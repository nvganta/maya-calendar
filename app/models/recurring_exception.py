import uuid
from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class RecurringEventException(Base):
    """
    Stores per-occurrence overrides for recurring events.

    - is_cancelled=True, new_start_time=None  → skip this occurrence
    - is_cancelled=False, new_start_time=set  → move this occurrence to a different time
    """
    __tablename__ = "recurring_event_exceptions"
    __table_args__ = (
        Index("ix_recur_exceptions_event_date", "event_id", "exception_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # The original date of the occurrence being overridden
    exception_date: Mapped[date] = mapped_column(Date, nullable=False)

    # If True, this occurrence is skipped entirely
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # If set, this occurrence uses these times instead of the rule's calculated times
    new_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    new_end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    event: Mapped["Event"] = relationship(back_populates="exceptions")  # noqa: F821
