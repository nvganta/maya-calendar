from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Maya integration (required — startup fails if missing to prevent auth bypass)
    MAYA_CLIENT_ID: str
    MAYA_CLIENT_SECRET: str
    MAYA_API_URL: str = "http://localhost:8000"

    # LLM
    LLM_PROVIDER: str = "openai"  # must be "openai" or "anthropic"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # App
    APP_NAME: str = "Maya Calendar Agent"
    DEBUG: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
