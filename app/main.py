import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.maya import router as maya_router
from app.api.events import router as events_router
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(title=settings.APP_NAME)

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


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "calendar"}
