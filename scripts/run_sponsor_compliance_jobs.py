#!/usr/bin/env python3
"""Dispatch day-9 sponsor absence alerts and SMS change reminders."""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend_stub"))

from sponsor_licence_compliance import (  # noqa: E402
    evaluate_day9_absence_alerts,
    refresh_sms_change_alert_statuses,
)
from core.notifications import queue_notification  # noqa: E402


def _connect():
    import psycopg2

    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required")
    return psycopg2.connect(url)


def _tenant_ids(conn) -> list[int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT tenant_id
            FROM employee_sponsor_profiles
            WHERE is_sponsored_worker = TRUE
            """
        )
        return [row[0] for row in cur.fetchall()]


def _queue_notification(conn, tenant_id: int, channel: str, subject: str, body: str, payload: dict) -> None:
    try:
        purpose = "compliance" if channel == "email" else "general"
        queue_notification(
            conn=conn,
            tenant_id=tenant_id,
            channel=channel,
            subject=subject,
            body=body,
            payload=payload,
            purpose=purpose,
        )
    except Exception as exc:  # notifications table may not exist in all environments yet
        print(json.dumps({"warning": "notification_queue_unavailable", "error": str(exc), "payload": payload}))


def main() -> int:
    as_of = date.today()
    conn = _connect()
    total_absence = 0
    total_sms = 0
    try:
        for tenant_id in _tenant_ids(conn):
            alerts = evaluate_day9_absence_alerts(tenant_id=tenant_id, as_of=as_of, conn=conn)
            for alert in alerts:
                subject = "ShiftSwift HR: Day 9 sponsor absence alert — Home Office reporting may be required"
                body = (
                    f"Sponsored worker #{alert['employee_id']} has reached "
                    f"{alert['consecutive_working_days']} consecutive unexcused working-day absences. "
                    "Review immediately and report to the Home Office if required within 10 consecutive working days."
                )
                for channel in alert.get("channels", ["email"]):
                    _queue_notification(conn, tenant_id, channel, subject, body, alert)
                total_absence += 1
            total_sms += refresh_sms_change_alert_statuses(tenant_id=tenant_id, as_of=as_of, conn=conn)
    finally:
        conn.close()
    print(json.dumps({"absence_alerts_generated": total_absence, "sms_statuses_updated": total_sms}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
