"""Offboarding workflows — ACAS appeal window and sponsorship cessation."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from core.events import emit_event

ACAS_APPEAL_DAYS = 21


def start_offboarding(
    *,
    tenant_id: int,
    employee_id: int,
    reason: str,
    grievance_case_id: int | None,
    actor_username: str,
    actor_role: str,
    conn: Any,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(esp.is_sponsored_worker, e.is_sponsored, FALSE)
            FROM employees e
            LEFT JOIN employee_sponsor_profiles esp
              ON esp.tenant_id = e.tenant_id AND esp.employee_id = e.id
            WHERE e.tenant_id = %s AND e.id = %s
            """,
            (tenant_id, employee_id),
        )
        row = cur.fetchone()
        is_sponsored = bool(row[0]) if row else False

        appeal_deadline = date.today() + timedelta(days=ACAS_APPEAL_DAYS)
        cur.execute(
            """
            INSERT INTO offboarding_workflows (
              tenant_id, employee_id, grievance_case_id, reason,
              acas_appeal_deadline, sponsorship_cessation_required
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, status, acas_appeal_deadline, sponsorship_cessation_required, started_at
            """,
            (tenant_id, employee_id, grievance_case_id, reason, appeal_deadline, is_sponsored),
        )
        wf = cur.fetchone()
        workflow_id = wf[0]
    conn.commit()

    emit_event(
        conn=conn,
        tenant_id=tenant_id,
        event_type="offboarding.started",
        entity_type="offboarding_workflows",
        entity_id=workflow_id,
        payload={
            "workflow_id": workflow_id,
            "employee_id": employee_id,
            "reason": reason,
            "sponsorship_cessation_required": is_sponsored,
            "acas_appeal_deadline": appeal_deadline.isoformat(),
        },
        actor_username=actor_username,
        actor_role=actor_role,
    )
    return {
        "id": workflow_id,
        "employee_id": employee_id,
        "status": wf[1],
        "acas_appeal_deadline": wf[2].isoformat() if wf[2] else None,
        "sponsorship_cessation_required": wf[3],
        "started_at": wf[4].isoformat() if wf[4] else None,
    }


def list_workflows(*, tenant_id: int, conn: Any, limit: int = 100) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.id, w.employee_id, w.grievance_case_id, w.reason, w.status,
                   w.acas_appeal_deadline, w.sponsorship_cessation_required,
                   w.sponsorship_cessation_reported_at, w.sponsorship_cessation_reference,
                   w.started_at, e.first_name, e.last_name, e.department
            FROM offboarding_workflows w
            JOIN employees e ON e.id = w.employee_id AND e.tenant_id = w.tenant_id
            WHERE w.tenant_id = %s
            ORDER BY w.started_at DESC
            LIMIT %s
            """,
            (tenant_id, limit),
        )
        items = []
        for row in cur.fetchall():
            employee_name = " ".join(filter(None, [row[10], row[11]])).strip()
            items.append(
                {
                    "id": row[0],
                    "employee_id": row[1],
                    "employee_name": employee_name or str(row[1]),
                    "employee_department": row[12],
                    "grievance_case_id": row[2],
                    "reason": row[3],
                    "status": row[4],
                    "acas_appeal_deadline": row[5].isoformat() if row[5] else None,
                    "sponsorship_cessation_required": row[6],
                    "sponsorship_cessation_reported_at": row[7].isoformat() if row[7] else None,
                    "sponsorship_cessation_reference": row[8],
                    "started_at": row[9].isoformat() if row[9] else None,
                }
            )
        return items


def report_sponsorship_cessation(
    *,
    tenant_id: int,
    workflow_id: int,
    report_reference: str,
    actor_username: str,
    conn: Any,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE offboarding_workflows
            SET sponsorship_cessation_reported_at = NOW(),
                sponsorship_cessation_reference = %s,
                status = 'completed',
                completed_at = NOW()
            WHERE tenant_id = %s AND id = %s
            RETURNING id, employee_id, sponsorship_cessation_reference, status
            """,
            (report_reference, tenant_id, workflow_id),
        )
        row = cur.fetchone()
    if not row:
        raise LookupError("offboarding workflow not found")
    conn.commit()
    return {
        "id": row[0],
        "employee_id": row[1],
        "sponsorship_cessation_reference": row[2],
        "status": row[3],
    }
