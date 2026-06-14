"""Master impersonation token tests."""

from __future__ import annotations

import sys
from pathlib import Path

import jwt

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from auth_service import create_impersonation_access_token, decode_token
from config import Settings


def _settings() -> Settings:
    return Settings(
        app_env="development",
        jwt_secret="test-secret-key-with-enough-length-123456",
        jwt_access_minutes=60,
        jwt_refresh_days=7,
        master_customer_id="999",
        cors_allow_origins=["http://localhost:5173"],
        trusted_hosts=["localhost"],
        force_https=False,
        login_rate_limit=10,
        login_rate_window_seconds=900,
        max_upload_bytes=10485760,
        database_url=None,
        use_db=False,
    )


def test_impersonation_token_has_expected_claims() -> None:
    settings = _settings()
    token, expires_in = create_impersonation_access_token(
        settings,
        master_username="admin@shiftswifthr.co.uk",
        tenant_id=42,
        expires_minutes=60,
    )
    assert expires_in == 3600
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    assert payload["role"] == "hr"
    assert payload["tenant_id"] == "42"
    assert payload["impersonation"] is True
    assert payload["impersonated_by"] == "admin@shiftswifthr.co.uk"


def test_decode_impersonation_token() -> None:
    settings = _settings()
    token, _ = create_impersonation_access_token(
        settings,
        master_username="admin@shiftswifthr.co.uk",
        tenant_id=7,
    )
    user = decode_token(settings, token, expected_type="access")
    assert user.role == "hr"
    assert user.tenant_id == "7"
    assert user.impersonated_by == "admin@shiftswifthr.co.uk"
