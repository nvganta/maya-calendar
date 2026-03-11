import hmac
import hashlib
import time
from fastapi import Request, HTTPException


TIMESTAMP_TOLERANCE = 300  # 5 minutes


def verify_maya_signature(body: str, secret: str, signature: str, timestamp: str) -> bool:
    """Verify HMAC-SHA256 signature from Maya."""
    # Check timestamp freshness
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    if abs(time.time() - ts) > TIMESTAMP_TOLERANCE:
        return False

    # Recreate and compare signature
    message = f"{timestamp}.{body}"
    expected = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


async def require_maya_signature(request: Request) -> str:
    """FastAPI dependency that verifies Maya's HMAC signature on incoming requests."""
    from app.core.config import get_settings
    settings = get_settings()

    client_id = request.headers.get("X-Maya-Client-ID", "")
    signature = request.headers.get("X-Maya-Signature", "")
    timestamp = request.headers.get("X-Maya-Timestamp", "")

    if client_id != settings.MAYA_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Invalid client ID")

    body = (await request.body()).decode("utf-8")

    if not verify_maya_signature(body, settings.MAYA_CLIENT_SECRET, signature, timestamp):
        raise HTTPException(status_code=401, detail="Invalid signature")

    return body
