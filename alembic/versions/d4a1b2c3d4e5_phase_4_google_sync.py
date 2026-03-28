"""Phase 4: Google Calendar sync models

Revision ID: d4a1b2c3d4e5
Revises: c9d348162306
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "d4a1b2c3d4e5"
down_revision = "c9d348162306"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Google OAuth tokens — one per user
    op.create_table(
        "google_oauth_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("google_email", sa.String(255), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_google_oauth_user", "google_oauth_tokens", ["user_id"], unique=True)

    # External event mapping — links internal events to Google/Outlook event IDs
    op.create_table(
        "external_event_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("internal_event_id", UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_provider", sa.String(50), nullable=False),
        sa.Column("external_event_id", sa.String(500), nullable=False),
        sa.Column("external_calendar_id", sa.String(500), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_mapping_event_provider", "external_event_mappings", ["internal_event_id", "external_provider"])
    op.create_index("ix_mapping_external", "external_event_mappings", ["external_provider", "external_event_id"])

    # Sync queue — async push operations to external calendars
    op.create_table(
        "sync_queue_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_event_id", sa.String(500), nullable=True),
        sa.Column("external_provider", sa.String(50), nullable=False, server_default="google"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sync_queue_pending", "sync_queue_items", ["status", "created_at"])
    op.create_index("ix_sync_queue_user", "sync_queue_items", ["user_id", "status"])


def downgrade() -> None:
    op.drop_table("sync_queue_items")
    op.drop_table("external_event_mappings")
    op.drop_table("google_oauth_tokens")
