"""Employee notes — HR internal (encrypted) and employee-visible messages."""

from __future__ import annotations

from typing import Any, Literal

from core.crypto import decrypt_text, encrypt_text, encryption_configured
from employee_audit import log_employee_data_event
from modules.employees.repository import fetch_employee

NoteVisibility = Literal["hr_internal", "employee_visible"]
VISIBILITY_CHOICES = frozenset({"hr_internal", "employee_visible"})
MAX_NOTE_LENGTH = 4000


def _normalize_body(body: str) -> str:
    text = (body or "").strip()
    if not text:
        raise ValueError("Note text is required")
    if len(text) > MAX_NOTE_LENGTH:
        raise ValueError(f"Note must be {MAX_NOTE_LENGTH} characters or fewer")
    return text


def _store_body(*, body: str, visibility: NoteVisibility) -> str:
    if visibility == "hr_internal":
        if not encryption_configured():
            raise ValueError("ENCRYPTION_KEY is not configured — cannot save HR-only notes")
        return encrypt_text(body)
    return body


def _read_body(*, stored: str, visibility: NoteVisibility) -> str:
    if visibility == "hr_internal":
        return decrypt_text(stored)
    return stored


def _note_row(
    *,
    note_id: int,
    visibility: str,
    stored_body: str,
    created_by: str,
    created_by_role: str,
    created_at: Any,
    include_body: bool,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": note_id,
        "visibility": visibility,
        "created_by": created_by,
        "created_by_role": created_by_role,
        "created_at": created_at.isoformat() if created_at else None,
    }
    if include_body:
        item["body"] = _read_body(stored=stored_body, visibility=visibility)  # type: ignore[arg-type]
    return item


def create_note(
    *,
    tenant_id: int,
    employee_id: int,
    body: str,
    visibility: str,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> dict[str, Any]:
    if visibility not in VISIBILITY_CHOICES:
        raise ValueError("visibility must be hr_internal or employee_visible")
    if not fetch_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn):
        raise LookupError("employee not found")

    normalized = _normalize_body(body)
    stored = _store_body(body=normalized, visibility=visibility)  # type: ignore[arg-type]

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO employee_notes (
              tenant_id, employee_id, visibility, body, created_by, created_by_role
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, visibility, body, created_by, created_by_role, created_at
            """,
            (tenant_id, employee_id, visibility, stored, actor_username, actor_role),
        )
        row = cur.fetchone()

    log_employee_data_event(
        tenant_id=tenant_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action="create",
        entity_type="employee_note",
        entity_id=row[0],
        field_name=visibility,
        new_value=normalized[:120],
        ip_address=ip_address,
        user_agent=user_agent,
        conn=conn,
    )
    conn.commit()
    return _note_row(
        note_id=row[0],
        visibility=row[1],
        stored_body=row[2],
        created_by=row[3],
        created_by_role=row[4],
        created_at=row[5],
        include_body=True,
    )


def list_notes_for_hr(
    *,
    tenant_id: int,
    employee_id: int,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> list[dict[str, Any]]:
    if not fetch_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn):
        raise LookupError("employee not found")

    log_employee_data_event(
        tenant_id=tenant_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action="view",
        entity_type="employee_note",
        entity_id=employee_id,
        ip_address=ip_address,
        user_agent=user_agent,
        conn=conn,
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, visibility, body, created_by, created_by_role, created_at
            FROM employee_notes
            WHERE tenant_id = %s AND employee_id = %s
            ORDER BY created_at DESC, id DESC
            """,
            (tenant_id, employee_id),
        )
        rows = cur.fetchall()

    return [
        _note_row(
            note_id=note_id,
            visibility=visibility,
            stored_body=stored_body,
            created_by=created_by,
            created_by_role=created_by_role,
            created_at=created_at,
            include_body=True,
        )
        for note_id, visibility, stored_body, created_by, created_by_role, created_at in rows
    ]


def list_notes_for_employee(
    *,
    tenant_id: int,
    employee_id: int,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> list[dict[str, Any]]:
    log_employee_data_event(
        tenant_id=tenant_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action="view",
        entity_type="employee_note",
        entity_id=employee_id,
        field_name="employee_visible",
        ip_address=ip_address,
        user_agent=user_agent,
        conn=conn,
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, visibility, body, created_by, created_by_role, created_at
            FROM employee_notes
            WHERE tenant_id = %s
              AND employee_id = %s
              AND visibility = 'employee_visible'
            ORDER BY created_at DESC, id DESC
            """,
            (tenant_id, employee_id),
        )
        rows = cur.fetchall()

    return [
        _note_row(
            note_id=note_id,
            visibility=visibility,
            stored_body=stored_body,
            created_by=created_by,
            created_by_role=created_by_role,
            created_at=created_at,
            include_body=True,
        )
        for note_id, visibility, stored_body, created_by, created_by_role, created_at in rows
    ]
