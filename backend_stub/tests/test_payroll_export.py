"""Unit tests for BrightPay / Xero CSV payroll export."""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from modules.payroll_export.service import (
    EMPLOYEE_CSV_COLUMNS,
    HOURS_CSV_COLUMNS,
    _pair_punch_hours,
    build_employees_csv,
    build_hours_csv,
    payroll_export_info,
)


def test_payroll_export_info_lists_partners() -> None:
    info = payroll_export_info()
    assert "BrightPay" in {p["name"] for p in info["partners"]}
    assert info["exports"]["employees_csv"].endswith("employees.csv")


@patch("modules.payroll_export.service.list_employees")
def test_build_employees_csv_includes_active_staff(mock_list: MagicMock) -> None:
    mock_list.return_value = [
        {
            "id": 1,
            "first_name": "Alex",
            "last_name": "Smith",
            "email": "alex@example.com",
            "phone": "",
            "ni_number": "AB123456C",
            "date_of_birth": "1990-01-01",
            "start_date": "2024-06-01",
            "job_title": "Chef",
            "department": "Kitchen",
            "employment_type": "full_time",
            "salary": 28000,
            "status": "active",
            "home_address": "1 High Street",
            "work_location": "Main site",
        },
        {"id": 2, "first_name": "Left", "last_name": "Staff", "status": "terminated"},
    ]
    conn = MagicMock()
    csv_body = build_employees_csv(tenant_id=1, conn=conn)
    lines = csv_body.strip().splitlines()
    assert lines[0] == ",".join(EMPLOYEE_CSV_COLUMNS)
    assert "Alex,Smith" in lines[1]
    assert all("Left" not in line for line in lines[1:])


def test_pair_punch_hours_computes_duration() -> None:
    punched_at_in = datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc)
    punched_at_out = datetime(2026, 6, 10, 17, 30, tzinfo=timezone.utc)
    punches = [
        (1, "Alex", "Smith", "in", punched_at_in),
        (1, "Alex", "Smith", "out", punched_at_out),
    ]
    rows = _pair_punch_hours(punches)
    assert len(rows) == 1
    emp_id, first, last, day, clock_in, clock_out, hours = rows[0]
    assert emp_id == 1
    assert first == "Alex"
    assert last == "Smith"
    assert day == date(2026, 6, 10)
    assert hours == 8.5


def test_build_hours_csv_writes_header_and_row() -> None:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    punched_at_in = datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc)
    punched_at_out = datetime(2026, 6, 10, 17, 0, tzinfo=timezone.utc)
    cursor.fetchall.return_value = [
        (1, "Alex", "Smith", "in", punched_at_in),
        (1, "Alex", "Smith", "out", punched_at_out),
    ]
    csv_body = build_hours_csv(
        tenant_id=1,
        conn=conn,
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 30),
    )
    lines = csv_body.strip().splitlines()
    assert lines[0] == ",".join(HOURS_CSV_COLUMNS)
    assert "Alex,Smith,2026-06-10,09:00,17:00,8.00" in lines[1]
