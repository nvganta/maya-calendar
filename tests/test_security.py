"""Tests for HMAC signature verification."""

import hashlib
import hmac
import time

import pytest

from app.core.security import verify_maya_signature


CLIENT_ID = "test-client-id"


def _sign(body: str, timestamp: str, key: str = CLIENT_ID) -> str:
    """Create a valid HMAC signature."""
    message = f"{timestamp}.{body}"
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


class TestVerifyMayaSignature:
    def test_valid_signature(self):
        body = '{"maya_user_id": 1}'
        ts = str(int(time.time()))
        sig = _sign(body, ts)
        assert verify_maya_signature(body, CLIENT_ID, sig, ts) is True

    def test_invalid_signature(self):
        body = '{"maya_user_id": 1}'
        ts = str(int(time.time()))
        assert verify_maya_signature(body, CLIENT_ID, "bad-signature", ts) is False

    def test_wrong_client_id(self):
        body = '{"maya_user_id": 1}'
        ts = str(int(time.time()))
        sig = _sign(body, ts, key="wrong-key")
        assert verify_maya_signature(body, CLIENT_ID, sig, ts) is False

    def test_expired_timestamp(self):
        body = '{"maya_user_id": 1}'
        ts = str(int(time.time()) - 600)  # 10 minutes ago
        sig = _sign(body, ts)
        assert verify_maya_signature(body, CLIENT_ID, sig, ts) is False

    def test_invalid_timestamp(self):
        body = '{"maya_user_id": 1}'
        assert verify_maya_signature(body, CLIENT_ID, "sig", "not-a-number") is False

    def test_tampered_body(self):
        body = '{"maya_user_id": 1}'
        ts = str(int(time.time()))
        sig = _sign(body, ts)
        # Tamper with the body
        assert verify_maya_signature('{"maya_user_id": 2}', CLIENT_ID, sig, ts) is False
