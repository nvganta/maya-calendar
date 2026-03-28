import uuid
from datetime import datetime, timezone
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, Text, DateTime, ForeignKey, Index, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


# Token encryption — key loaded lazily from settings
_fernet: Fernet | None = None
_fernet_checked: bool = False


def _get_fernet() -> Fernet | None:
    global _fernet, _fernet_checked
    if not _fernet_checked:
        _fernet_checked = True
        from app.core.config import get_settings
        key = get_settings().TOKEN_ENCRYPTION_KEY
        if key:
            _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


class EncryptedText(TypeDecorator):
    """SQLAlchemy type that transparently encrypts/decrypts values using Fernet.

    - On write: encrypts plaintext before storing in the DB
    - On read: decrypts ciphertext; gracefully handles legacy unencrypted values
    - If no encryption key is configured, values pass through as plaintext
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        f = _get_fernet()
        if f:
            return f.encrypt(value.encode()).decode()
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        f = _get_fernet()
        if f:
            try:
                return f.decrypt(value.encode()).decode()
            except InvalidToken:
                # Legacy unencrypted value — return as-is for safe rollout
                return value
        return value


class GoogleOAuthToken(Base):
    __tablename__ = "google_oauth_tokens"
    __table_args__ = (
        Index("ix_google_oauth_user", "user_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Tokens are encrypted at rest via EncryptedText TypeDecorator — automatic on all reads/writes
    access_token: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
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
