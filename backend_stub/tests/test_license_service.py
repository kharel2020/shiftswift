"""License hold and Direct Debit grace period tests."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from license_service import DD_GRACE_DAYS, days_until_hold  # noqa: E402


def test_grace_days_default() -> None:
    assert DD_GRACE_DAYS == 7


def test_days_until_hold_counts_down() -> None:
    failed = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    now = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    assert days_until_hold(payment_failed_at=failed, as_of=now) == DD_GRACE_DAYS - 3


def test_days_until_hold_expired() -> None:
    failed = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    now = failed + timedelta(days=DD_GRACE_DAYS + 1)
    assert days_until_hold(payment_failed_at=failed, as_of=now) <= 0
