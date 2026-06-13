"""Disciplinary case management — encrypted notes and audit trail."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from typing import Any

from core.crypto import decrypt_text, encrypt_text, encryption_configured
from core.events import emit_event
from modules.disciplinary.constants import MISCONDUCT_LABELS, STATUS_LABELS


def _next_case_reference(conn: Any, tenant_id: int) -> str:
    year = datetime.now(timezone.utc).year
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM disciplinary_cases
            WHERE tenant_id = %s AND case_reference LIKE %s
            """,
            (tenant_id, f"DIS-{year}-%"),
        )
        count = int(cur.fetchone()[0]) + 1
    return f"DIS-{year}-{count:03d}"


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
            INSERT INTO disciplinary_case_audit (
              tenant_id, case_id, action, actor_username, actor_role,
              field_name, detail, ip_address
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (tenant_id, case_id, action, actor_username, actor_role, field_name, detail, ip_address),
        )
    conn.commit()


_CASE_SELECT = """
  dc.id, dc.employee_id, dc.case_reference, dc.status, dc.misconduct_type,
  dc.opened_at, dc.closed_at, dc.close_outcome, dc.opened_by, dc.assigned_investigator,
  dc.misconduct_type_other, dc.severity, dc.date_reported, dc.linked_absence_context
"""

_CASE_SELECT_WITH_EMPLOYEE = f"""
  {_CASE_SELECT.strip()},
  e.first_name, e.last_name, e.department
"""

_CASE_RETURNING = """
  id, employee_id, case_reference, status, misconduct_type,
  opened_at, closed_at, close_outcome, opened_by, assigned_investigator,
  misconduct_type_other, severity, date_reported, linked_absence_context
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
    misconduct_key = row[4]
    misconduct_other = row[10]
    misconduct_label = MISCONDUCT_LABELS.get(misconduct_key, misconduct_key)
    if misconduct_key == "other" and misconduct_other:
        misconduct_label = f"Other — {misconduct_other}"
    employee_name = None
    employee_department = None
    if len(row) > 14:
        first_name, last_name, employee_department = row[14], row[15], row[16]
        if first_name or last_name:
            employee_name = " ".join(filter(None, [first_name, last_name])).strip()
    return {
        "id": row[0],
        "employee_id": row[1],
        "case_reference": row[2],
        "status": row[3],
        "status_label": STATUS_LABELS.get(row[3], row[3]),
        "misconduct_type": misconduct_key,
        "misconduct_type_label": misconduct_label,
        "misconduct_type_other": misconduct_other,
        "opened_at": row[5].isoformat() if row[5] else None,
        "date_reported": _iso_date(row[12]),
        "closed_at": row[6].isoformat() if row[6] else None,
        "close_outcome": row[7],
        "opened_by": row[8],
        "assigned_investigator": row[9],
        "severity": row[11] or "medium",
        "linked_absence_context": row[13],
        "employee_name": employee_name,
        "employee_department": employee_department,
    }


def build_case_timeline(case: dict[str, Any]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    if case.get("date_reported") or case.get("opened_at"):
        timeline.append(
            {
                "key": "opened",
                "label": "Case opened",
                "date": case.get("date_reported") or (case.get("opened_at") or "")[:10],
                "detail": case.get("opened_by") or "HR",
                "state": "done",
            }
        )
    if case.get("status") in ("investigation", "hearing", "appeal", "closed"):
        timeline.append(
            {
                "key": "investigation",
                "label": "Investigation",
                "date": (case.get("opened_at") or "")[:10] or case.get("date_reported"),
                "detail": case.get("assigned_investigator") or case.get("opened_by") or "Investigator assigned",
                "state": "done" if case.get("status") != "investigation" or case.get("assigned_investigator") else "current",
            }
        )
    if case.get("status") in ("hearing", "appeal", "closed"):
        timeline.append(
            {
                "key": "hearing",
                "label": "Disciplinary hearing",
                "date": None,
                "detail": "Formal hearing stage",
                "state": "done" if case.get("status") in ("appeal", "closed") else "current",
            }
        )
    if case.get("status") == "closed":
        timeline.append(
            {
                "key": "resolved",
                "label": "Case closed",
                "date": (case.get("closed_at") or "")[:10],
                "detail": case.get("close_outcome") or "Closed",
                "state": "done",
            }
        )
    else:
        timeline.append(
            {
                "key": "resolution",
                "label": "Awaiting outcome",
                "date": None,
                "detail": "Investigation in progress",
                "state": "todo",
            }
        )
    return timeline


def list_cases(*, tenant_id: int, conn: Any, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = f"""
        SELECT {_CASE_SELECT_WITH_EMPLOYEE}
        FROM disciplinary_cases dc
        JOIN employees e ON e.id = dc.employee_id AND e.tenant_id = dc.tenant_id
        WHERE dc.tenant_id = %s
    """
    params: list[Any] = [tenant_id]
    if status:
        query += " AND dc.status = %s"
        params.append(status)
    query += " ORDER BY dc.opened_at DESC LIMIT %s"
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(query, params)
        return [_case_row(row) for row in cur.fetchall()]


def count_open_cases(*, tenant_id: int, conn: Any) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM disciplinary_cases
            WHERE tenant_id = %s AND status <> 'closed'
            """,
            (tenant_id,),
        )
        return int(cur.fetchone()[0])


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


def get_case(*, tenant_id: int, case_id: int, conn: Any) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_CASE_SELECT_WITH_EMPLOYEE}
            FROM disciplinary_cases dc
            JOIN employees e ON e.id = dc.employee_id AND e.tenant_id = dc.tenant_id
            WHERE dc.tenant_id = %s AND dc.id = %s
            """,
            (tenant_id, case_id),
        )
        row = cur.fetchone()
    if not row:
        raise LookupError("disciplinary case not found")
    case = _case_row(row)
    case["timeline"] = build_case_timeline(case)
    return case


def create_case(
    *,
    tenant_id: int,
    employee_id: int,
    misconduct_type: str,
    misconduct_type_other: str | None,
    date_reported: date,
    severity: str,
    linked_absence_context: str | None,
    assigned_investigator: str | None,
    initial_note: str | None,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    conn: Any,
) -> dict[str, Any]:
    if not encryption_configured():
        raise ValueError("ENCRYPTION_KEY must be configured for disciplinary notes")

    case_reference = _next_case_reference(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO disciplinary_cases (
              tenant_id, employee_id, case_reference, misconduct_type, misconduct_type_other,
              date_reported, severity, linked_absence_context,
              opened_by, assigned_investigator
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {_CASE_RETURNING}
            """,
            (
                tenant_id,
                employee_id,
                case_reference,
                misconduct_type,
                misconduct_type_other,
                date_reported,
                severity,
                linked_absence_context,
                actor_username,
                assigned_investigator or actor_username,
            ),
        )
        row = cur.fetchone()
        case_id = row[0]
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
        event_type="disciplinary.opened",
        entity_type="disciplinary_case",
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
            INSERT INTO disciplinary_case_notes (tenant_id, case_id, encrypted_body, note_type, created_by)
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
            FROM disciplinary_case_notes
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
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE disciplinary_cases
            SET status = 'closed', closed_at = NOW(), close_outcome = %s, updated_at = NOW()
            WHERE tenant_id = %s AND id = %s
            RETURNING {_CASE_RETURNING}
            """,
            (close_outcome, tenant_id, case_id),
        )
        cur.fetchone()
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
        event_type="disciplinary.closed",
        entity_type="disciplinary_case",
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
            "Misconduct",
            "Severity",
            "Status",
            "Date reported",
            "Investigator",
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
                case.get("misconduct_type_label"),
                case.get("severity"),
                case.get("status_label"),
                case.get("date_reported") or "",
                case.get("assigned_investigator") or "",
                (case.get("closed_at") or "")[:10],
                case.get("close_outcome") or "",
            ]
        )
    return buffer.getvalue()
