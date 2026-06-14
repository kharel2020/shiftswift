"""Platform master dashboard helpers."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from modules.master.service import (
    _format_last_active,
    _is_test_tenant,
    _staff_label,
    display_status,
)


def test_display_status_trialing() -> None:
    assert display_status(subscription_status="trialing") == "trialing"


def test_display_status_active() -> None:
    assert display_status(subscription_status="active") == "active"


def test_display_status_overdue_from_payment_hold() -> None:
    assert display_status(subscription_status="payment_hold") == "overdue"


def test_display_status_overdue_from_license_hold() -> None:
    assert display_status(subscription_status="active", license_state="hold") == "overdue"


def test_format_last_active_today() -> None:
    now = datetime(2026, 6, 10, 16, 52, tzinfo=timezone.utc)
    last = datetime(2026, 6, 10, 10, 0, tzinfo=timezone.utc)
    result = _format_last_active(last, as_of=now)
    assert result["tone"] == "good"
    assert "Today" in result["label"]


def test_is_test_tenant_example_email() -> None:
    assert _is_test_tenant("Acme Ltd", "test1781083937@example.com")


def test_staff_label_no_hr_login() -> None:
    assert (
        _staff_label(
            active_count=0,
            staff_limit=40,
            hr_login_email="owner@acme.co.uk",
            hr_last_login=None,
        )
        == "no HR login yet"
    )
