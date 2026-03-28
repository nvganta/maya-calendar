import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ExternalEventMapping(Base):
    __tablename__ = "external_event_mappings"
    __table_args__ = (
        UniqueConstraint("internal_event_id", "external_provider", name="uq_mapping_event_provider"),
        Index("ix_mapping_external", "external_provider", "external_event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    internal_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    external_provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "google", "outlook"
    external_event_id: Mapped[str] = mapped_column(String(500), nullable=False)
    external_calendar_id: Mapped[str | None] = mapped_column(String(500), nullable=True)  # e.g. "primary"
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    event: Mapped["Event"] = relationship(back_populates="external_mappings")  # noqa: F821
