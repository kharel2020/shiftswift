"""Cross-module event listeners — compliance ↔ grievance ↔ offboarding."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from sponsor_licence_compliance import SMS_REPORTING_WINDOW_DAYS


def dispatch_event(
    *,
    conn: Any,
    tenant_id: int,
    event_type: str,
    payload: dict[str, Any],
    actor_username: str | None,
    actor_role: str | None,
) -> None:
    handlers = {
        "employee.status_changed": _on_employee_status_changed,
        "grievance.opened": _on_grievance_opened,
        "grievance.closed": _on_grievance_closed,
        "offboarding.started": _on_offboarding_started,
    }
    handler = handlers.get(event_type)
    if handler:
        handler(
            conn=conn,
            tenant_id=tenant_id,
            payload=payload,
            actor_username=actor_username,
            actor_role=actor_role,
        )
    _queue_webhooks(conn=conn, tenant_id=tenant_id, event_type=event_type, payload=payload)


def _is_sponsored(conn: Any, tenant_id: int, employee_id: int) -> bool:
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
        return bool(row[0]) if row else False


def _on_employee_status_changed(
    *,
    conn: Any,
    tenant_id: int,
    payload: dict[str, Any],
    actor_username: str | None,
    actor_role: str | None,
) -> None:
    employee_id = int(payload["employee_id"])
    new_status = payload.get("new_status")
    old_status = payload.get("old_status")
    reason = payload.get("reason") or "status change"

    if new_status == old_status:
        return

    if new_status == "suspended" and _is_sponsored(conn, tenant_id, employee_id):
        deadline = date.today() + timedelta(days=SMS_REPORTING_WINDOW_DAYS)
        description = (
            f"Action required: sponsored employee #{employee_id} suspended ({reason}). "
            "Report to Home Office SMS within 10 working days."
        )
        _create_reporting_trigger(
            conn=conn,
            tenant_id=tenant_id,
            employee_id=employee_id,
            trigger_type="suspension_sms_report",
            source_module="employees",
            source_entity_type="employee",
            source_entity_id=employee_id,
            description=description,
            deadline_date=deadline,
        )
        _queue_compliance_notification(conn, tenant_id, employee_id, description)

    if new_status == "terminated" and _is_sponsored(conn, tenant_id, employee_id):
        from modules.offboarding.service import start_offboarding

        start_offboarding(
            conn=conn,
            tenant_id=tenant_id,
            employee_id=employee_id,
            reason=f"termination:{reason}",
            grievance_case_id=payload.get("grievance_case_id"),
            actor_username=actor_username or "system",
            actor_role=actor_role or "system",
        )


def _on_grievance_opened(
    *,
    conn: Any,
    tenant_id: int,
    payload: dict[str, Any],
    actor_username: str | None,
    actor_role: str | None,
) -> None:
    if not payload.get("linked_absence_context"):
        return
    employee_id = int(payload["employee_id"])
    if not _is_sponsored(conn, tenant_id, employee_id):
        return
    _queue_compliance_notification(
        conn,
        tenant_id,
        employee_id,
        f"Grievance {payload.get('case_reference')} opened with absence/dispute context — "
        "monitor consecutive absence days for sponsor reporting.",
    )


def _on_grievance_closed(
    *,
    conn: Any,
    tenant_id: int,
    payload: dict[str, Any],
    actor_username: str | None,
    actor_role: str | None,
) -> None:
    outcome = payload.get("close_outcome")
    if outcome not in {"dismissal", "resignation"}:
        return
    from modules.offboarding.service import start_offboarding

    start_offboarding(
        conn=conn,
        tenant_id=tenant_id,
        employee_id=int(payload["employee_id"]),
        reason=f"grievance_{outcome}",
        grievance_case_id=int(payload["case_id"]),
        actor_username=actor_username or "system",
        actor_role=actor_role or "system",
    )


def _on_offboarding_started(
    *,
    conn: Any,
    tenant_id: int,
    payload: dict[str, Any],
    actor_username: str | None,
    actor_role: str | None,
) -> None:
    if not payload.get("sponsorship_cessation_required"):
        return
    deadline = date.today() + timedelta(days=SMS_REPORTING_WINDOW_DAYS)
    _create_reporting_trigger(
        conn=conn,
        tenant_id=tenant_id,
        employee_id=int(payload["employee_id"]),
        trigger_type="sponsorship_cessation",
        source_module="offboarding",
        source_entity_type="offboarding_workflows",
        source_entity_id=int(payload["workflow_id"]),
        description="Generate and submit Sponsorship Cessation Report to Home Office SMS.",
        deadline_date=deadline,
    )


def _create_reporting_trigger(
    *,
    conn: Any,
    tenant_id: int,
    employee_id: int,
    trigger_type: str,
    source_module: str,
    source_entity_type: str | None,
    source_entity_id: int | None,
    description: str,
    deadline_date: date,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sponsor_reporting_triggers (
              tenant_id, employee_id, trigger_type, source_module,
              source_entity_type, source_entity_id, description, deadline_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_id,
                employee_id,
                trigger_type,
                source_module,
                source_entity_type,
                source_entity_id,
                description,
                deadline_date,
            ),
        )
    conn.commit()


def _queue_compliance_notification(
    conn: Any,
    tenant_id: int,
    employee_id: int,
    message: str,
) -> None:
    try:
        from core.email_templates import compliance_alert_email
        from core.notifications import queue_email_notification

        content = compliance_alert_email(message=message)
        queue_email_notification(
            conn=conn,
            tenant_id=tenant_id,
            subject=content.subject,
            body=content.text,
            purpose="compliance",
            payload={"employee_id": employee_id, "module": "compliance", "html_body": content.html},
        )
    except Exception:
        conn.rollback()


def _queue_webhooks(
    *,
    conn: Any,
    tenant_id: int,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, target_url, secret
            FROM webhook_subscriptions
            WHERE tenant_id = %s AND is_active = TRUE
              AND (%s = ANY(event_types) OR cardinality(event_types) = 0)
            """,
            (tenant_id, event_type),
        )
        subs = cur.fetchall()
    for sub_id, _url, _secret in subs:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notifications (tenant_id, channel, subject, body, payload, status)
                VALUES (%s, 'webhook', %s, %s, %s::jsonb, 'queued')
                """,
                (
                    tenant_id,
                    f"webhook:{event_type}",
                    f"Deliver webhook subscription #{sub_id}",
                    json.dumps({"subscription_id": sub_id, "event_type": event_type, "payload": payload}),
                ),
            )
        conn.commit()
