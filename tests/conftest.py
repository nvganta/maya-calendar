"""
Shared test fixtures.

Uses an in-memory SQLite database for fast, isolated tests.
PostgreSQL-specific types (ARRAY) are handled by the JSON fallback in the model.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import event as sa_event, String, JSON
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.database import Base
from app.models.user import User
from app.models.event import Event
from app.models.reminder import Reminder  # noqa: F401
from app.models.recurring_exception import RecurringEventException  # noqa: F401


# --- SQLite compatibility: map PostgreSQL-specific types → JSON ---
# This lets us run tests without PostgreSQL.
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

@sa_event.listens_for(Base.metadata, "column_reflect")
def _convert_pg_types(inspector, table, column_info):
    col_type = column_info.get("type")
    if isinstance(col_type, (ARRAY, JSONB)):
        column_info["type"] = JSON()


# --- Engine + Session ---

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    # For SQLite: temporarily override PG-specific column types for DDL creation
    # We swap ARRAY -> JSON and JSONB -> JSON, then restore after
    from app.models.event import Event as EventModel
    from app.models.user import User as UserModel

    overrides = []
    # ARRAY(String) tags column
    tags_col = EventModel.__table__.c.tags
    if hasattr(tags_col.type, 'item_type'):
        overrides.append((tags_col, tags_col.type))
        tags_col.type = JSON()
    # JSONB preferences column
    prefs_col = UserModel.__table__.c.preferences
    if isinstance(prefs_col.type, JSONB):
        overrides.append((prefs_col, prefs_col.type))
        prefs_col.type = JSON()

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as session:
            yield session

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    finally:
        for col, original_type in overrides:
            col.type = original_type
        await engine.dispose()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        maya_user_id=1,
        email="test@example.com",
        name="Test User",
        timezone="America/New_York",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_events(db_session: AsyncSession, test_user: User) -> list[Event]:
    """Create a few sample events for testing."""
    now = datetime.now(timezone.utc)
    events = [
        Event(
            user_id=test_user.id,
            title="Team Standup",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=1, minutes=30),
        ),
        Event(
            user_id=test_user.id,
            title="Dentist Appointment",
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=4),
            location="123 Main St",
        ),
        Event(
            user_id=test_user.id,
            title="Team Meeting",
            start_time=now + timedelta(days=1, hours=2),
            end_time=now + timedelta(days=1, hours=3),
        ),
    ]
    for e in events:
        db_session.add(e)
    await db_session.commit()
    for e in events:
        await db_session.refresh(e)
    return events
