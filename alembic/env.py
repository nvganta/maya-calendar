import asyncio
import os
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# Load .env for local dev
from dotenv import load_dotenv
load_dotenv()

# Import models so Alembic can detect them
from app.core.database import Base
from app.models import User, Event, Reminder, GoogleOAuthToken, ExternalEventMapping, SyncQueueItem  # noqa: F401

config = context.config

# Get DATABASE_URL from environment (don't depend on pydantic settings for migrations)
database_url = os.getenv("DATABASE_URL", "")
if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is required for migrations")

config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(database_url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
