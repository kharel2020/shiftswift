"""Employee data access — full profile, section updates, documents."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from modules.employees.constants import COMPLIANCE_REPORTING_FIELDS, SECTION_FIELDS

EMPLOYEE_COLUMN_NAMES = (
    "id",
    "first_name",
    "last_name",
    "email",
    "job_title",
    "salary",
    "work_location",
    "start_date",
    "status",
    "is_sponsored",
    "created_at",
    "updated_at",
    "phone",
    "date_of_birth",
    "home_address",
    "ni_number",
    "department",
    "employment_type",
    "probation_end_date",
    "emergency_contact_name",
    "emergency_contact_phone",
    "emergency_contact_relationship",
    "termination_date",
    "termination_reason",
)

EMPLOYEE_COLUMNS = ", ".join(EMPLOYEE_COLUMN_NAMES)
EMPLOYEE_SELECT = ", ".join(f"e.{name}" for name in EMPLOYEE_COLUMN_NAMES)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _row_to_employee(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "first_name": row[1],
        "last_name": row[2],
        "email": row[3],
        "job_title": row[4],
        "salary": float(row[5]) if row[5] is not None else None,
        "work_location": row[6],
        "start_date": _iso(row[7]),
        "status": row[8],
        "is_sponsored": row[9],
        "created_at": _iso(row[10]),
        "updated_at": _iso(row[11]),
        "phone": row[12],
        "date_of_birth": _iso(row[13]),
        "home_address": row[14],
        "ni_number": row[15],
        "department": row[16],
        "employment_type": row[17] or "full_time",
        "probation_end_date": _iso(row[18]),
        "emergency_contact_name": row[19],
        "emergency_contact_phone": row[20],
        "emergency_contact_relationship": row[21],
        "termination_date": _iso(row[22]),
        "termination_reason": row[23],
    }


def _row_to_sponsor(row: tuple[Any, ...] | None) -> dict[str, Any]:
    if not row:
        return {
            "is_sponsored_worker": False,
            "visa_type": None,
            "visa_expiry_date": None,
            "share_code": None,
            "cos_reference": None,
            "rtw_status": "pending",
        }
    return {
        "is_sponsored_worker": row[0],
        "visa_type": row[1],
        "visa_expiry_date": _iso(row[2]),
        "share_code": row[3],
        "cos_reference": row[4],
        "rtw_status": row[5] or "pending",
    }


def fetch_employee(*, tenant_id: int, employee_id: int, conn: Any) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {EMPLOYEE_SELECT} FROM employees e WHERE e.tenant_id = %s AND e.id = %s",
            (tenant_id, employee_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        employee = _row_to_employee(row)
        cur.execute(
            """
            SELECT is_sponsored_worker, visa_type, visa_expiry_date, share_code,
                   cos_reference, rtw_status
            FROM employee_sponsor_profiles
            WHERE tenant_id = %s AND employee_id = %s
            """,
            (tenant_id, employee_id),
        )
        sponsor = _row_to_sponsor(cur.fetchone())
    employee["sponsorship"] = sponsor
    return employee


def list_employee_summaries(*, tenant_id: int, conn: Any, limit: int = 200) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {EMPLOYEE_SELECT}
            FROM employees e
            WHERE e.tenant_id = %s
            ORDER BY e.last_name, e.first_name
            LIMIT %s
            """,
            (tenant_id, limit),
        )
        return [_row_to_employee(row) for row in cur.fetchall()]


def update_employee_fields(
    *,
    tenant_id: int,
    employee_id: int,
    updates: dict[str, Any],
    conn: Any,
) -> dict[str, Any]:
    if not updates:
        employee = fetch_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
        if not employee:
            raise LookupError("employee not found")
        return employee

    updates = {**updates, "updated_at": datetime.utcnow()}
    sets = ", ".join(f"{key} = %s" for key in updates)
    values = list(updates.values()) + [tenant_id, employee_id]
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE employees SET {sets}
            WHERE tenant_id = %s AND id = %s
            RETURNING {EMPLOYEE_COLUMNS}
            """,
            values,
        )
        row = cur.fetchone()
        if not row:
            raise LookupError("employee not found")
        conn.commit()
    return _row_to_employee(row)


def update_sponsorship_fields(
    *,
    tenant_id: int,
    employee_id: int,
    updates: dict[str, Any],
    conn: Any,
) -> dict[str, Any]:
    employee = fetch_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    if not employee:
        raise LookupError("employee not found")

    is_sponsored = updates.get("is_sponsored")
    if is_sponsored is None:
        is_sponsored = employee.get("is_sponsored", False)
    else:
        is_sponsored = bool(is_sponsored)
        if is_sponsored != employee.get("is_sponsored"):
            update_employee_fields(
                tenant_id=tenant_id,
                employee_id=employee_id,
                updates={"is_sponsored": is_sponsored},
                conn=conn,
            )

    sponsor_updates = {
        k: updates[k]
        for k in ("visa_type", "visa_expiry_date", "share_code", "cos_reference", "rtw_status")
        if k in updates
    }

    if sponsor_updates or "is_sponsored" in updates:
        from modules.employees.service import sync_sponsor_profile

        sync_sponsor_profile(
            tenant_id=tenant_id,
            employee_id=employee_id,
            is_sponsored=is_sponsored,
            conn=conn,
            visa_type=sponsor_updates.get("visa_type"),
            visa_expiry_date=sponsor_updates.get("visa_expiry_date"),
            share_code=sponsor_updates.get("share_code"),
            cos_reference=sponsor_updates.get("cos_reference"),
        )
        if "rtw_status" in sponsor_updates:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE employee_sponsor_profiles
                    SET rtw_status = %s, updated_at = NOW()
                    WHERE tenant_id = %s AND employee_id = %s
                    """,
                    (sponsor_updates["rtw_status"], tenant_id, employee_id),
                )
                conn.commit()

    employee = fetch_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    if not employee:
        raise LookupError("employee not found")
    return employee["sponsorship"]


def list_employee_documents(*, tenant_id: int, employee_id: int, conn: Any) -> list[dict[str, Any]]:
    from modules.documents.service import list_employee_documents as list_docs

    return list_docs(tenant_id=tenant_id, employee_id=employee_id, conn=conn)


def create_employee_document(
    *,
    tenant_id: int,
    employee_id: int,
    data: dict[str, Any],
    uploaded_by: str,
    conn: Any,
) -> dict[str, Any]:
    from modules.documents.service import create_employee_document as create_doc

    return create_doc(
        tenant_id=tenant_id,
        employee_id=employee_id,
        data=data,
        uploaded_by=uploaded_by,
        conn=conn,
    )


def delete_employee_document(
    *,
    tenant_id: int,
    employee_id: int,
    document_id: int,
    conn: Any,
) -> None:
    from modules.documents.service import delete_employee_document as delete_doc

    delete_doc(
        tenant_id=tenant_id,
        employee_id=employee_id,
        document_id=document_id,
        conn=conn,
    )


def section_field_names(section: str) -> tuple[str, ...]:
    if section == "compliance_reporting":
        return COMPLIANCE_REPORTING_FIELDS
    return SECTION_FIELDS.get(section, ())
