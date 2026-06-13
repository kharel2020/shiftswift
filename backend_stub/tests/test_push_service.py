"""Unit tests for Web Push subscription storage and dedupe."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from modules.push import service as push_service


def test_push_not_configured_without_keys(monkeypatch) -> None:
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    assert push_service.push_configured() is False
    assert push_service.push_config_payload()["enabled"] is False


def test_record_push_sent_dedupes() -> None:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [(1,), None]

    assert push_service.record_push_sent(
        tenant_id=1,
        employee_id=2,
        notification_key="shift_start:99",
        conn=conn,
    )
    assert (
        push_service.record_push_sent(
            tenant_id=1,
            employee_id=2,
            notification_key="shift_start:99",
            conn=conn,
        )
        is False
    )


def test_send_employee_push_skips_when_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    conn = MagicMock()
    result = push_service.send_employee_push(
        tenant_id=1,
        employee_id=2,
        notification_key="shift_start:1",
        title="Test",
        body="Body",
        url="https://app.example/punch.html",
        conn=conn,
    )
    assert result["skipped"] == "not_configured"


@patch("modules.push.service.send_push")
@patch("modules.push.service.list_subscriptions")
@patch("modules.push.service.record_push_sent")
@patch("modules.push.service.push_configured", return_value=True)
def test_send_employee_push_delivers_to_devices(
    _configured,
    record_sent,
    list_subs,
    send_push,
    monkeypatch,
) -> None:
    record_sent.return_value = True
    list_subs.return_value = [
        {"id": 1, "endpoint": "https://push.example/1", "p256dh": "k", "auth": "a"}
    ]
    send_push.return_value = True
    conn = MagicMock()

    result = push_service.send_employee_push(
        tenant_id=1,
        employee_id=2,
        notification_key="shift_start:5",
        title="Clock in",
        body="Shift started",
        url="https://app.example/punch.html",
        conn=conn,
    )
    assert result["sent"] == 1
    send_push.assert_called_once()
