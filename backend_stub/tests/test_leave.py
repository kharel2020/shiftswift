"""Unit tests for leave request workflows."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from modules.leave.service import (
    count_weekdays,
    create_leave_request,
    leave_balance,
    review_leave_request,
    sync_approved_leave_to_sponsor_absence,
)


def test_count_weekdays_excludes_weekends() -> None:
    assert count_weekdays(start=date(2026, 6, 8), end=date(2026, 6, 12)) == 5.0
    assert count_weekdays(start=date(2026, 6, 13), end=date(2026, 6, 14)) == 0.0


def test_create_leave_request_inserts_pending_row() -> None:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [(1,), None, (28.0,), (0.0, 0.0), (42,)]
    cursor.fetchall.return_value = [
        (
            42,
            1,
            "Alex",
            "Smith",
            "annual",
            date(2026, 7, 6),
            date(2026, 7, 10),
            5.0,
            "Holiday",
            "pending",
            None,
            None,
            None,
            None,
        )
    ]

    item = create_leave_request(
        tenant_id=1,
        employee_id=1,
        leave_type="annual",
        start_date=date(2026, 7, 6),
        end_date=date(2026, 7, 10),
        reason="Holiday",
        conn=conn,
    )

    assert item["id"] == 42
    assert item["status"] == "pending"
    assert item["days_requested"] == 5.0
    conn.commit.assert_called_once()


def test_leave_balance_subtracts_used_and_pending() -> None:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [(28.0,), (6.0, 2.0)]

    balance = leave_balance(tenant_id=1, employee_id=1, conn=conn, year=2026)

    assert balance["allowance_days"] == 28.0
    assert balance["used_days"] == 6.0
    assert balance["pending_days"] == 2.0
    assert balance["remaining_days"] == 20.0


def test_review_leave_request_approves_pending() -> None:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [
        (1, "sick", 1.0, "pending"),
        (date(2026, 7, 6), date(2026, 7, 6)),
        (False,),
    ]
    cursor.fetchall.return_value = [
        (
            1,
            1,
            "Alex",
            "Smith",
            "annual",
            date(2026, 7, 6),
            date(2026, 7, 6),
            1.0,
            None,
            "approved",
            "hr.admin",
            None,
            None,
            None,
        )
    ]

    item = review_leave_request(
        tenant_id=1,
        request_id=1,
        decision="approved",
        reviewed_by="hr.admin",
        review_note=None,
        conn=conn,
    )

    assert item["status"] == "approved"
    conn.commit.assert_called_once()


def test_sync_approved_leave_skips_non_sponsored() -> None:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.return_value = (False,)

    synced = sync_approved_leave_to_sponsor_absence(
        tenant_id=1,
        employee_id=1,
        request_id=42,
        leave_type="annual",
        start_date=date(2026, 7, 6),
        end_date=date(2026, 7, 6),
        conn=conn,
    )

    assert synced == 0
