import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.maya import router as maya_router
from app.api.events import router as events_router
from app.api.google import router as google_router
from app.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background workers on startup, clean up on shutdown."""
    from app.services.reminder_worker import run_reminder_worker
    reminder_task = asyncio.create_task(run_reminder_worker())
    logger.info("Calendar agent started.")
    try:
        yield
    finally:
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass
        logger.info("Calendar agent shut down.")


settings = get_settings()

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# CORS — allow Maya frontend + local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.agentmaya.io",
        "https://agentmaya.io",
        "https://calendar.agentmaya.io",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(maya_router)
app.include_router(events_router, prefix="/api/events", tags=["events"])
app.include_router(google_router, prefix="/api/google", tags=["google"])


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "calendar"}
