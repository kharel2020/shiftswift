"""Rota attendance evaluation tests."""

from __future__ import annotations

import sys
from datetime import date, datetime, time, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from modules.rota.attendance import evaluate_shift_attendance


def test_evaluate_shift_attendance_no_show() -> None:
    shift = {
        "id": 1,
        "employee_id": 1,
        "shift_date": "2026-06-08",
        "start_time": "09:00",
        "end_time": "17:00",
        "employee_name": "Alex",
    }
    now = datetime(2026, 6, 8, 18, 0, tzinfo=timezone.utc)
    result = evaluate_shift_attendance(shift=shift, punches=[], now=now)
    assert result["attendance_status"] == "no_show"


def test_evaluate_shift_attendance_late() -> None:
    shift = {
        "id": 2,
        "employee_id": 1,
        "shift_date": "2026-06-08",
        "start_time": "09:00",
        "end_time": "17:00",
        "employee_name": "Alex",
    }
    punches = [{"punch_type": "in", "punched_at": datetime(2026, 6, 8, 9, 20, tzinfo=timezone.utc)}]
    now = datetime(2026, 6, 8, 10, 0, tzinfo=timezone.utc)
    result = evaluate_shift_attendance(shift=shift, punches=punches, now=now)
    assert result["attendance_status"] == "late"


def test_evaluate_shift_attendance_attended() -> None:
    shift = {
        "id": 3,
        "employee_id": 1,
        "shift_date": "2026-06-08",
        "start_time": "09:00",
        "end_time": "17:00",
        "employee_name": "Alex",
    }
    punches = [{"punch_type": "in", "punched_at": datetime(2026, 6, 8, 8, 55, tzinfo=timezone.utc)}]
    now = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    result = evaluate_shift_attendance(shift=shift, punches=punches, now=now)
    assert result["attendance_status"] == "attended"
