"""Tests for platform master tenant ops."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dev_credentials import DEV_MASTER_PASSWORD, DEV_MASTER_USERNAME
from main import app

client = TestClient(app)


def _master_headers() -> dict[str, str]:
    login = client.post(
        "/auth/master-login",
        json={"username": DEV_MASTER_USERNAME, "password": DEV_MASTER_PASSWORD},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.skipif(not DEV_MASTER_USERNAME, reason="master credentials not configured")
def test_master_settings_and_audit_endpoints():
    headers = _master_headers()
    settings = client.get("/master/settings", headers=headers)
    assert settings.status_code == 200
    body = settings.json()
    assert "master_require_mfa" in body
    assert "database_configured" in body

    keys = client.get("/master/api-keys", headers=headers)
    assert keys.status_code == 200
    assert "stripe" in keys.json()

    audit = client.get("/master/audit-log?limit=5", headers=headers)
    assert audit.status_code == 200
    assert "items" in audit.json()


@pytest.mark.skipif(not DEV_MASTER_USERNAME, reason="master credentials not configured")
def test_master_account_profile():
    headers = _master_headers()
    res = client.get("/master/account", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == DEV_MASTER_USERNAME
