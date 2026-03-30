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

    # Google Calendar OAuth (optional — sync disabled if not set)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8001/api/google/callback"

    # Token encryption key for OAuth tokens at rest (Fernet key, base64-encoded 32 bytes)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    TOKEN_ENCRYPTION_KEY: str = ""

    # JWT for frontend sessions (issued after SSO validation)
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 1440  # 24 hours

    # App
    APP_NAME: str = "Maya Calendar Agent"
    DEBUG: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
