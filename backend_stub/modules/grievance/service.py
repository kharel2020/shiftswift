"""Grievance case management — encrypted notes, ACAS milestones, audit trail."""

from __future__ import annotations

import calendar
import csv
import io
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.crypto import decrypt_text, encrypt_text, encryption_configured
from core.events import emit_event
from modules.grievance.constants import ALLEGATION_LABELS, STATUS_LABELS

ACAS_APPEAL_DAYS = 21


def calculate_acas_deadline(notification_date: date) -> date:
    """ACAS early conciliation deadline — one calendar month plus 14 days."""
    year, month, day = notification_date.year, notification_date.month, notification_date.day
    month += 1
    if month > 12:
        month = 1
        year += 1
    last_day = calendar.monthrange(year, month)[1]
    safe_day = min(day, last_day)
    one_month_later = date(year, month, safe_day)
    return one_month_later + timedelta(days=14)


def days_until(deadline: date | None) -> int | None:
    if not deadline:
        return None
    return (deadline - date.today()).days


def deadline_alert_level(deadline: date | None) -> str | None:
    remaining = days_until(deadline)
    if remaining is None:
        return None
    if remaining < 0:
        return "overdue"
    if remaining <= 14:
        return "warn"
    return "ok"


def _next_case_reference(conn: Any, tenant_id: int) -> str:
    year = datetime.now(timezone.utc).year
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM grievance_cases
            WHERE tenant_id = %s AND case_reference LIKE %s
            """,
            (tenant_id, f"GRV-{year}-%"),
        )
        count = int(cur.fetchone()[0]) + 1
    return f"GRV-{year}-{count:03d}"


def _log_case_audit(
    *,
    conn: Any,
    tenant_id: int,
    case_id: int,
    action: str,
    actor_username: str,
    actor_role: str,
    field_name: str | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO grievance_case_audit (
              tenant_id, case_id, action, actor_username, actor_role,
              field_name, detail, ip_address
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (tenant_id, case_id, action, actor_username, actor_role, field_name, detail, ip_address),
        )
    conn.commit()


_CASE_SELECT = f"""
  gc.id, gc.employee_id, gc.case_reference, gc.status, gc.allegation_type,
  gc.opened_at, gc.closed_at, gc.close_outcome, gc.acas_deadline, gc.appeal_deadline,
  gc.is_anonymous_to_manager, gc.linked_absence_context, gc.opened_by, gc.assigned_investigator,
  gc.allegation_type_other, gc.severity, gc.date_received, gc.acas_notification_date
"""

_CASE_SELECT_WITH_EMPLOYEE = f"""
  {_CASE_SELECT.strip()},
  e.first_name, e.last_name, e.department
"""

_CASE_RETURNING = """
  id, employee_id, case_reference, status, allegation_type,
  opened_at, closed_at, close_outcome, acas_deadline, appeal_deadline,
  is_anonymous_to_manager, linked_absence_context, opened_by, assigned_investigator,
  allegation_type_other, severity, date_received, acas_notification_date
"""


def _iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _case_row(row: tuple[Any, ...]) -> dict[str, Any]:
    allegation_key = row[4]
    allegation_other = row[14]
    allegation_label = ALLEGATION_LABELS.get(allegation_key, allegation_key)
    if allegation_key == "other" and allegation_other:
        allegation_label = f"Other — {allegation_other}"
    deadline_date = row[8] if isinstance(row[8], date) else None
    employee_name = None
    employee_department = None
    if len(row) > 18:
        first_name, last_name, employee_department = row[18], row[19], row[20]
        if first_name or last_name:
            employee_name = " ".join(filter(None, [first_name, last_name])).strip()
    return {
        "id": row[0],
        "employee_id": row[1],
        "case_reference": row[2],
        "status": row[3],
        "status_label": STATUS_LABELS.get(row[3], row[3]),
        "allegation_type": allegation_key,
        "allegation_type_label": allegation_label,
        "allegation_type_other": allegation_other,
        "opened_at": row[5].isoformat() if row[5] else None,
        "date_received": _iso_date(row[16]),
        "closed_at": row[6].isoformat() if row[6] else None,
        "close_outcome": row[7],
        "acas_deadline": _iso_date(deadline_date),
        "acas_notification_date": _iso_date(row[17]),
        "appeal_deadline": _iso_date(row[9]),
        "is_anonymous_to_manager": row[10],
        "linked_absence_context": row[11],
        "opened_by": row[12],
        "assigned_investigator": row[13],
        "severity": row[15] or "medium",
        "employee_name": employee_name,
        "employee_department": employee_department,
        "acas_days_remaining": days_until(deadline_date),
        "acas_deadline_alert": deadline_alert_level(deadline_date),
    }


def list_cases(*, tenant_id: int, conn: Any, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = f"""
        SELECT {_CASE_SELECT_WITH_EMPLOYEE}
        FROM grievance_cases gc
        JOIN employees e ON e.id = gc.employee_id AND e.tenant_id = gc.tenant_id
        WHERE gc.tenant_id = %s
    """
    params: list[Any] = [tenant_id]
    if status:
        query += " AND gc.status = %s"
        params.append(status)
    query += " ORDER BY gc.opened_at DESC LIMIT %s"
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(query, params)
        return [_case_row(row) for row in cur.fetchall()]


def list_investigators(*, tenant_id: int, conn: Any) -> list[dict[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT username, role FROM app_users
            WHERE tenant_id = %s
            ORDER BY username
            """,
            (tenant_id,),
        )
        return [
            {"value": username, "label": f"{username} ({role.replace('_', ' ').title()})"}
            for username, role in cur.fetchall()
        ]


def build_case_timeline(case: dict[str, Any]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    if case.get("date_received") or case.get("opened_at"):
        timeline.append(
            {
                "key": "opened",
                "label": "Case opened",
                "date": case.get("date_received") or (case.get("opened_at") or "")[:10],
                "detail": case.get("opened_by") or "HR",
                "state": "done",
            }
        )
    if case.get("status") in ("investigation", "hearing", "appeal", "closed"):
        timeline.append(
            {
                "key": "investigation",
                "label": "Investigation started",
                "date": (case.get("opened_at") or "")[:10] or case.get("date_received"),
                "detail": case.get("assigned_investigator") or case.get("opened_by") or "Investigator assigned",
                "state": "done" if case.get("status") != "investigation" or case.get("assigned_investigator") else "current",
            }
        )
    if case.get("acas_notification_date"):
        deadline = case.get("acas_deadline") or ""
        timeline.append(
            {
                "key": "acas",
                "label": "ACAS notified",
                "date": case.get("acas_notification_date"),
                "detail": f"Deadline {deadline}" if deadline else "Early conciliation",
                "state": "done" if case.get("status") in ("hearing", "appeal", "closed") else "current",
            }
        )
    if case.get("status") == "closed":
        timeline.append(
            {
                "key": "resolved",
                "label": "Case resolved",
                "date": (case.get("closed_at") or "")[:10],
                "detail": case.get("close_outcome") or "Closed",
                "state": "done",
            }
        )
    else:
        timeline.append(
            {
                "key": "resolution",
                "label": "Awaiting resolution",
                "date": None,
                "detail": "Investigation in progress",
                "state": "todo",
            }
        )
    return timeline


def get_case(*, tenant_id: int, case_id: int, conn: Any) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_CASE_SELECT_WITH_EMPLOYEE}
            FROM grievance_cases gc
            JOIN employees e ON e.id = gc.employee_id AND e.tenant_id = gc.tenant_id
            WHERE gc.tenant_id = %s AND gc.id = %s
            """,
            (tenant_id, case_id),
        )
        row = cur.fetchone()
    if not row:
        raise LookupError("grievance case not found")
    case = _case_row(row)
    case["timeline"] = build_case_timeline(case)
    return case


def create_case(
    *,
    tenant_id: int,
    employee_id: int,
    allegation_type: str,
    allegation_type_other: str | None,
    date_received: date,
    acas_notification_date: date | None,
    severity: str,
    linked_absence_context: str | None,
    is_anonymous_to_manager: bool,
    assigned_investigator: str | None,
    initial_note: str | None,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    conn: Any,
) -> dict[str, Any]:
    if not encryption_configured():
        raise ValueError("ENCRYPTION_KEY must be configured for grievance notes")

    case_reference = _next_case_reference(conn, tenant_id)
    acas_deadline = calculate_acas_deadline(acas_notification_date) if acas_notification_date else None

    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO grievance_cases (
              tenant_id, employee_id, case_reference, allegation_type, allegation_type_other,
              date_received, acas_notification_date, acas_deadline, severity,
              linked_absence_context, is_anonymous_to_manager,
              opened_by, assigned_investigator
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {_CASE_RETURNING}
            """,
            (
                tenant_id,
                employee_id,
                case_reference,
                allegation_type,
                allegation_type_other,
                date_received,
                acas_notification_date,
                acas_deadline,
                severity,
                linked_absence_context,
                is_anonymous_to_manager,
                actor_username,
                assigned_investigator or actor_username,
            ),
        )
        row = cur.fetchone()
        case_id = row[0]
        if acas_deadline:
            cur.execute(
                """
                INSERT INTO acas_milestones (tenant_id, case_id, milestone_type, due_date)
                VALUES (%s, %s, 'early_conciliation', %s)
                """,
                (tenant_id, case_id, acas_deadline),
            )
    conn.commit()
    case = get_case(tenant_id=tenant_id, case_id=case_id, conn=conn)

    if initial_note:
        add_note(
            tenant_id=tenant_id,
            case_id=case_id,
            body=initial_note,
            note_type="investigation",
            actor_username=actor_username,
            actor_role=actor_role,
            ip_address=ip_address,
            conn=conn,
        )

    _log_case_audit(
        conn=conn,
        tenant_id=tenant_id,
        case_id=case_id,
        action="create",
        actor_username=actor_username,
        actor_role=actor_role,
        ip_address=ip_address,
    )

    emit_event(
        conn=conn,
        tenant_id=tenant_id,
        event_type="grievance.opened",
        entity_type="grievance_case",
        entity_id=case_id,
        payload={
            "case_id": case_id,
            "case_reference": case_reference,
            "employee_id": employee_id,
            "linked_absence_context": linked_absence_context,
        },
        actor_username=actor_username,
        actor_role=actor_role,
    )
    return case


def add_note(
    *,
    tenant_id: int,
    case_id: int,
    body: str,
    note_type: str,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    conn: Any,
) -> dict[str, Any]:
    get_case(tenant_id=tenant_id, case_id=case_id, conn=conn)
    encrypted = encrypt_text(body)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO grievance_case_notes (tenant_id, case_id, encrypted_body, note_type, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, note_type, created_by, created_at
            """,
            (tenant_id, case_id, encrypted, note_type, actor_username),
        )
        row = cur.fetchone()
    conn.commit()
    _log_case_audit(
        conn=conn,
        tenant_id=tenant_id,
        case_id=case_id,
        action="upload" if note_type != "system" else "update",
        actor_username=actor_username,
        actor_role=actor_role,
        detail=f"note:{note_type}",
        ip_address=ip_address,
    )
    return {
        "id": row[0],
        "note_type": row[1],
        "created_by": row[2],
        "created_at": row[3].isoformat() if row[3] else None,
    }


def list_notes(
    *,
    tenant_id: int,
    case_id: int,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    conn: Any,
    include_body: bool = True,
) -> list[dict[str, Any]]:
    get_case(tenant_id=tenant_id, case_id=case_id, conn=conn)
    _log_case_audit(
        conn=conn,
        tenant_id=tenant_id,
        case_id=case_id,
        action="view",
        actor_username=actor_username,
        actor_role=actor_role,
        ip_address=ip_address,
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, encrypted_body, note_type, created_by, created_at
            FROM grievance_case_notes
            WHERE tenant_id = %s AND case_id = %s
            ORDER BY created_at DESC
            """,
            (tenant_id, case_id),
        )
        rows = cur.fetchall()
    items = []
    for note_id, encrypted, note_type, created_by, created_at in rows:
        item = {
            "id": note_id,
            "note_type": note_type,
            "created_by": created_by,
            "created_at": created_at.isoformat() if created_at else None,
        }
        if include_body:
            item["body"] = decrypt_text(encrypted)
        items.append(item)
    return items


def suspend_employee_from_case(
    *,
    tenant_id: int,
    case_id: int,
    reason: str,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    conn: Any,
) -> dict[str, Any]:
    case = get_case(tenant_id=tenant_id, case_id=case_id, conn=conn)
    employee_id = case["employee_id"]
    from modules.employees.service import after_employee_updated, get_employee_row

    old_row = get_employee_row(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    if not old_row:
        raise LookupError("employee not found")
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE employees SET status = 'suspended', updated_at = NOW()
            WHERE tenant_id = %s AND id = %s
            """,
            (tenant_id, employee_id),
        )
    conn.commit()
    new_row = get_employee_row(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    after_employee_updated(
        tenant_id=tenant_id,
        employee_id=employee_id,
        old_row=old_row,
        new_row=new_row or old_row,
        actor_username=actor_username,
        actor_role=actor_role,
        conn=conn,
        reason=f"grievance suspension: {reason}",
    )
    add_note(
        tenant_id=tenant_id,
        case_id=case_id,
        body=f"Employee suspended during investigation. Reason: {reason}",
        note_type="system",
        actor_username=actor_username,
        actor_role=actor_role,
        ip_address=ip_address,
        conn=conn,
    )
    return new_row or {}


def close_case(
    *,
    tenant_id: int,
    case_id: int,
    close_outcome: str,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    conn: Any,
) -> dict[str, Any]:
    case = get_case(tenant_id=tenant_id, case_id=case_id, conn=conn)
    appeal_deadline = date.today() + timedelta(days=ACAS_APPEAL_DAYS)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE grievance_cases
            SET status = 'closed', closed_at = NOW(), close_outcome = %s,
                appeal_deadline = %s, updated_at = NOW()
            WHERE tenant_id = %s AND id = %s
            RETURNING {_CASE_RETURNING}
            """,
            (close_outcome, appeal_deadline, tenant_id, case_id),
        )
        row = cur.fetchone()
    conn.commit()
    updated = get_case(tenant_id=tenant_id, case_id=case_id, conn=conn)
    _log_case_audit(
        conn=conn,
        tenant_id=tenant_id,
        case_id=case_id,
        action="close",
        actor_username=actor_username,
        actor_role=actor_role,
        field_name="close_outcome",
        detail=close_outcome,
        ip_address=ip_address,
    )
    emit_event(
        conn=conn,
        tenant_id=tenant_id,
        event_type="grievance.closed",
        entity_type="grievance_case",
        entity_id=case_id,
        payload={
            "case_id": case_id,
            "case_reference": case["case_reference"],
            "employee_id": case["employee_id"],
            "close_outcome": close_outcome,
        },
        actor_username=actor_username,
        actor_role=actor_role,
    )
    return updated


def export_cases_csv(*, tenant_id: int, conn: Any) -> str:
    cases = list_cases(tenant_id=tenant_id, conn=conn, limit=5000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Reference",
            "Employee",
            "Department",
            "Allegation",
            "Severity",
            "Status",
            "Date received",
            "ACAS notification",
            "ACAS deadline",
            "Investigator",
            "Anonymous to manager",
            "Closed at",
            "Outcome",
        ]
    )
    for case in cases:
        writer.writerow(
            [
                case.get("case_reference"),
                case.get("employee_name") or case.get("employee_id"),
                case.get("employee_department") or "",
                case.get("allegation_type_label"),
                case.get("severity"),
                case.get("status_label"),
                case.get("date_received") or "",
                case.get("acas_notification_date") or "",
                case.get("acas_deadline") or "",
                case.get("assigned_investigator") or "",
                "Yes" if case.get("is_anonymous_to_manager") else "No",
                (case.get("closed_at") or "")[:10],
                case.get("close_outcome") or "",
            ]
        )
    return buffer.getvalue()
