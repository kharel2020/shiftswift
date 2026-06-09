"""Grievance case management — encrypted notes, ACAS milestones, audit trail."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.crypto import decrypt_text, encrypt_text, encryption_configured
from core.events import emit_event

ACAS_INVESTIGATION_DAYS = 28
ACAS_APPEAL_DAYS = 21


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


def _case_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "employee_id": row[1],
        "case_reference": row[2],
        "status": row[3],
        "allegation_type": row[4],
        "opened_at": row[5].isoformat() if row[5] else None,
        "closed_at": row[6].isoformat() if row[6] else None,
        "close_outcome": row[7],
        "acas_deadline": row[8].isoformat() if row[8] else None,
        "appeal_deadline": row[9].isoformat() if row[9] else None,
        "is_anonymous_to_manager": row[10],
        "linked_absence_context": row[11],
        "opened_by": row[12],
        "assigned_investigator": row[13],
    }


def list_cases(*, tenant_id: int, conn: Any, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = """
        SELECT id, employee_id, case_reference, status, allegation_type, opened_at,
               closed_at, close_outcome, acas_deadline, appeal_deadline,
               is_anonymous_to_manager, linked_absence_context, opened_by, assigned_investigator
        FROM grievance_cases WHERE tenant_id = %s
    """
    params: list[Any] = [tenant_id]
    if status:
        query += " AND status = %s"
        params.append(status)
    query += " ORDER BY opened_at DESC LIMIT %s"
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(query, params)
        return [_case_row(row) for row in cur.fetchall()]


def get_case(*, tenant_id: int, case_id: int, conn: Any) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, employee_id, case_reference, status, allegation_type, opened_at,
                   closed_at, close_outcome, acas_deadline, appeal_deadline,
                   is_anonymous_to_manager, linked_absence_context, opened_by, assigned_investigator
            FROM grievance_cases WHERE tenant_id = %s AND id = %s
            """,
            (tenant_id, case_id),
        )
        row = cur.fetchone()
    if not row:
        raise LookupError("grievance case not found")
    return _case_row(row)


def create_case(
    *,
    tenant_id: int,
    employee_id: int,
    allegation_type: str,
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
    acas_deadline = date.today() + timedelta(days=ACAS_INVESTIGATION_DAYS)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO grievance_cases (
              tenant_id, employee_id, case_reference, allegation_type,
              acas_deadline, linked_absence_context, is_anonymous_to_manager,
              opened_by, assigned_investigator
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, employee_id, case_reference, status, allegation_type, opened_at,
                      closed_at, close_outcome, acas_deadline, appeal_deadline,
                      is_anonymous_to_manager, linked_absence_context, opened_by, assigned_investigator
            """,
            (
                tenant_id,
                employee_id,
                case_reference,
                allegation_type,
                acas_deadline,
                linked_absence_context,
                is_anonymous_to_manager,
                actor_username,
                assigned_investigator,
            ),
        )
        row = cur.fetchone()
        case_id = row[0]
        cur.execute(
            """
            INSERT INTO acas_milestones (tenant_id, case_id, milestone_type, due_date)
            VALUES (%s, %s, 'investigation_complete', %s),
                   (%s, %s, 'hearing_invitation', %s)
            """,
            (tenant_id, case_id, acas_deadline, tenant_id, case_id, acas_deadline - timedelta(days=7)),
        )
    conn.commit()
    case = _case_row(row)

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
            """
            UPDATE grievance_cases
            SET status = 'closed', closed_at = NOW(), close_outcome = %s,
                appeal_deadline = %s, updated_at = NOW()
            WHERE tenant_id = %s AND id = %s
            RETURNING id, employee_id, case_reference, status, allegation_type, opened_at,
                      closed_at, close_outcome, acas_deadline, appeal_deadline,
                      is_anonymous_to_manager, linked_absence_context, opened_by, assigned_investigator
            """,
            (close_outcome, appeal_deadline, tenant_id, case_id),
        )
        row = cur.fetchone()
    conn.commit()
    updated = _case_row(row)
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
