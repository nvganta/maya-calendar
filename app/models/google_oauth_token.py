import uuid
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from sqlalchemy import String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


# Token encryption — key loaded lazily from settings
_fernet: Fernet | None = None


def _get_fernet() -> Fernet | None:
    global _fernet
    if _fernet is None:
        from app.core.config import get_settings
        key = get_settings().TOKEN_ENCRYPTION_KEY
        if key:
            _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_token(plaintext: str) -> str:
    f = _get_fernet()
    if f:
        return f.encrypt(plaintext.encode()).decode()
    return plaintext  # no-op if encryption key not configured


def decrypt_token(ciphertext: str) -> str:
    f = _get_fernet()
    if f:
        return f.decrypt(ciphertext.encode()).decode()
    return ciphertext  # no-op if encryption key not configured


class GoogleOAuthToken(Base):
    __tablename__ = "google_oauth_tokens"
    __table_args__ = (
        Index("ix_google_oauth_user", "user_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Tokens are encrypted at rest via encrypt_token/decrypt_token
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    google_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)  # space-separated scope strings
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="google_oauth_token")  # noqa: F821
