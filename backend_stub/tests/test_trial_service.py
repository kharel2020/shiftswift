"""Tests for 14-day trial and upgrade reminders."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from trial_service import (  # noqa: E402
    DEFAULT_TRIAL_DAYS,
    _pick_reminder_key,
    days_until_trial_end,
)


def test_default_trial_is_14_days() -> None:
    assert DEFAULT_TRIAL_DAYS == 14


def test_days_until_trial_end() -> None:
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    assert days_until_trial_end(trial_ends_at=end, as_of=now) == 7


def test_pick_reminder_thresholds() -> None:
    assert _pick_reminder_key(10) is None
    assert _pick_reminder_key(7) == "7_day"
    assert _pick_reminder_key(3) == "3_day"
    assert _pick_reminder_key(1) == "1_day"
    assert _pick_reminder_key(0) == "expired"
    assert _pick_reminder_key(-1) == "expired"


def test_days_until_none_when_no_end() -> None:
    assert days_until_trial_end(trial_ends_at=None) is None
