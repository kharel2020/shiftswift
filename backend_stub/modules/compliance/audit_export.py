"""Sponsor licence audit export pack and expiry alert jobs."""

from __future__ import annotations

import json
from datetime import date
from typing import Any


def build_audit_export(*, tenant_id: int, employee_id: int | None, conn: Any) -> dict[str, Any]:
    """Compile RTW, SMS, absence, adverts, and reporting triggers for Home Office audit."""
    pack: dict[str, Any] = {
        "tenant_id": tenant_id,
        "employee_id": employee_id,
        "generated_on": date.today().isoformat(),
        "sections": {},
    }

    with conn.cursor() as cur:
        if employee_id:
            cur.execute(
                """
                SELECT id, check_date, outcome, expiry_date, content_sha256, storage_path
                FROM right_to_work_checks
                WHERE tenant_id = %s AND employee_id = %s ORDER BY check_date DESC
                """,
                (tenant_id, employee_id),
            )
            pack["sections"]["right_to_work_checks"] = [
                {
                    "id": r[0],
                    "check_date": r[1].isoformat() if r[1] else None,
                    "outcome": r[2],
                    "expiry_date": r[3].isoformat() if r[3] else None,
                    "content_sha256": r[4],
                    "storage_path": r[5],
                }
                for r in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT field_name, old_value, new_value, changed_at, sms_reporting_deadline, alert_status
                FROM sponsor_sms_change_log
                WHERE tenant_id = %s AND employee_id = %s ORDER BY changed_at DESC
                """,
                (tenant_id, employee_id),
            )
            pack["sections"]["sms_change_log"] = [
                {
                    "field_name": r[0],
                    "old_value": r[1],
                    "new_value": r[2],
                    "changed_at": r[3].isoformat() if r[3] else None,
                    "sms_reporting_deadline": r[4].isoformat() if r[4] else None,
                    "alert_status": r[5],
                }
                for r in cur.fetchall()
            ]
        else:
            pack["sections"]["right_to_work_checks"] = []
            pack["sections"]["sms_change_log"] = []

        cur.execute(
            """
            SELECT id, employee_id, consecutive_working_days, alert_status,
                   home_office_report_required_by, triggered_at
            FROM sponsor_absence_alerts
            WHERE tenant_id = %s
            ORDER BY triggered_at DESC LIMIT 200
            """,
            (tenant_id,),
        )
        pack["sections"]["absence_alerts"] = [
            {
                "id": r[0],
                "employee_id": r[1],
                "consecutive_working_days": r[2],
                "alert_status": r[3],
                "home_office_report_required_by": r[4].isoformat() if r[4] else None,
                "triggered_at": r[5].isoformat() if r[5] else None,
            }
            for r in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT job_title, platform, advert_url, posted_date, job_reference
            FROM recruitment_advertisement_records
            WHERE tenant_id = %s ORDER BY posted_date DESC LIMIT 100
            """,
            (tenant_id,),
        )
        pack["sections"]["advertisement_records"] = [
            {
                "job_title": r[0],
                "platform": r[1],
                "advert_url": r[2],
                "posted_date": r[3].isoformat() if r[3] else None,
                "job_reference": r[4],
            }
            for r in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT id, employee_id, trigger_type, description, deadline_date, status, created_at
            FROM sponsor_reporting_triggers
            WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 100
            """,
            (tenant_id,),
        )
        pack["sections"]["reporting_triggers"] = [
            {
                "id": r[0],
                "employee_id": r[1],
                "trigger_type": r[2],
                "description": r[3],
                "deadline_date": r[4].isoformat() if r[4] else None,
                "status": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
            }
            for r in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT event_type, entity_type, entity_id, payload, created_at
            FROM compliance_audit_events
            WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 500
            """,
            (tenant_id,),
        )
        pack["sections"]["compliance_audit_events"] = [
            {
                "event_type": r[0],
                "entity_type": r[1],
                "entity_id": r[2],
                "payload": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in cur.fetchall()
        ]

    pack["summary"] = {
        "rtw_checks": len(pack["sections"]["right_to_work_checks"]),
        "sms_changes": len(pack["sections"]["sms_change_log"]),
        "absence_alerts": len(pack["sections"]["absence_alerts"]),
        "adverts": len(pack["sections"]["advertisement_records"]),
        "reporting_triggers": len(pack["sections"]["reporting_triggers"]),
    }
    return pack


def evaluate_visa_expiry_alerts(*, tenant_id: int, as_of: date, conn: Any) -> list[dict[str, Any]]:
    thresholds = [90, 60, 30, 7]
    alerts: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        for days in thresholds:
            target = as_of.toordinal() + days
            target_date = date.fromordinal(target)
            cur.execute(
                """
                SELECT esp.employee_id, esp.visa_expiry_date, e.first_name, e.last_name
                FROM employee_sponsor_profiles esp
                JOIN employees e ON e.id = esp.employee_id AND e.tenant_id = esp.tenant_id
                WHERE esp.tenant_id = %s
                  AND esp.is_sponsored_worker = TRUE
                  AND esp.visa_expiry_date = %s
                """,
                (tenant_id, target_date),
            )
            for employee_id, expiry, first_name, last_name in cur.fetchall():
                alerts.append(
                    {
                        "employee_id": employee_id,
                        "employee_name": f"{first_name} {last_name}",
                        "visa_expiry_date": expiry.isoformat(),
                        "days_until_expiry": days,
                        "threshold": days,
                    }
                )
                from core.notifications import build_email_payload

                email_payload = build_email_payload(
                    tenant_id=tenant_id,
                    conn=conn,
                    purpose="compliance",
                    payload={
                        "employee_id": employee_id,
                        "days": days,
                        "type": "visa_expiry",
                    },
                )
                cur.execute(
                    """
                    INSERT INTO notifications (tenant_id, channel, subject, body, payload, status)
                    VALUES (%s, 'email', %s, %s, %s::jsonb, 'queued')
                    """,
                    (
                        tenant_id,
                        f"Visa expiry in {days} days",
                        f"Sponsored worker {first_name} {last_name} visa expires on {expiry.isoformat()}.",
                        json.dumps(email_payload),
                    ),
                )
    conn.commit()
    return alerts


def evaluate_rtw_expiry_alerts(*, tenant_id: int, as_of: date, conn: Any) -> list[dict[str, Any]]:
    thresholds = [90, 60, 30, 7]
    alerts: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        for days in thresholds:
            target_date = date.fromordinal(as_of.toordinal() + days)
            cur.execute(
                """
                SELECT DISTINCT ON (employee_id) employee_id, expiry_date, id
                FROM right_to_work_checks
                WHERE tenant_id = %s AND expiry_date = %s
                ORDER BY employee_id, check_date DESC
                """,
                (tenant_id, target_date),
            )
            for employee_id, expiry, check_id in cur.fetchall():
                alerts.append(
                    {
                        "employee_id": employee_id,
                        "rtw_check_id": check_id,
                        "expiry_date": expiry.isoformat(),
                        "days_until_expiry": days,
                    }
                )
    return alerts
