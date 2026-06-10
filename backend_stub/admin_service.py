"""Tenant admin workspace — profile, employees, document store."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from employee_audit import log_employee_data_event

ADVERT_PLATFORMS = [
    {"value": "GOV.UK Find a Job", "label": "GOV.UK Find a Job"},
    {"value": "Company careers site", "label": "Company careers site"},
    {"value": "Indeed", "label": "Indeed"},
    {"value": "LinkedIn", "label": "LinkedIn"},
    {"value": "Reed", "label": "Reed"},
    {"value": "Totaljobs", "label": "Totaljobs"},
    {"value": "Other", "label": "Other"},
]

DOCUMENT_CATEGORIES = [
    {"value": "general", "label": "General"},
    {"value": "policy", "label": "Policy & handbook"},
    {"value": "contract", "label": "Employment contract"},
    {"value": "rtw", "label": "Right to work"},
    {"value": "payroll", "label": "Payroll"},
    {"value": "disciplinary", "label": "Disciplinary"},
    {"value": "other", "label": "Other"},
]

EMPLOYEE_STATUSES = [
    {"value": "active", "label": "Active"},
    {"value": "onboarding", "label": "Onboarding"},
    {"value": "suspended", "label": "Suspended"},
    {"value": "inactive", "label": "Inactive"},
    {"value": "terminated", "label": "Terminated"},
]

TENANT_PROFILE_FIELDS = (
    "name",
    "trading_name",
    "company_number",
    "registered_address",
    "phone",
    "billing_email",
    "vat_number",
    "signatory_name",
    "signatory_title",
    "signatory_email",
)


from modules.employees.repository import EMPLOYEE_COLUMNS, _row_to_employee, fetch_employee, list_employee_summaries
from modules.employees.workspace import list_completion_summary


def get_tenant_profile(*, tenant_id: int, conn: Any) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, trading_name, company_number, registered_address, phone,
                   billing_email, vat_number, signatory_name, signatory_title, signatory_email,
                   subscription_plan, subscription_status, max_employees,
                   payroll_plan_id, payroll_enabled
            FROM tenants WHERE id = %s
            """,
            (tenant_id,),
        )
        row = cur.fetchone()
        if not row:
            raise LookupError("tenant not found")
        return {
            "id": row[0],
            "name": row[1],
            "trading_name": row[2],
            "company_number": row[3],
            "registered_address": row[4],
            "phone": row[5],
            "billing_email": row[6],
            "vat_number": row[7],
            "signatory_name": row[8],
            "signatory_title": row[9],
            "signatory_email": row[10],
            "subscription_plan": row[11],
            "subscription_status": row[12],
            "max_employees": row[13],
            "payroll_plan_id": row[14],
            "payroll_enabled": row[15],
        }


def update_tenant_profile(
    *,
    tenant_id: int,
    updates: dict[str, Any],
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> dict[str, Any]:
    allowed = {k: v for k, v in updates.items() if k in TENANT_PROFILE_FIELDS}
    if not allowed:
        return get_tenant_profile(tenant_id=tenant_id, conn=conn)

    sets = ", ".join(f"{key} = %s" for key in allowed)
    values = list(allowed.values()) + [tenant_id]
    with conn.cursor() as cur:
        cur.execute(f"UPDATE tenants SET {sets} WHERE id = %s", values)
        conn.commit()

    if allowed.get("registered_address"):
        try:
            from modules.time_punch.service import sync_primary_site_from_tenant_address

            sync_primary_site_from_tenant_address(tenant_id=tenant_id, conn=conn)
        except Exception:
            pass

    log_employee_data_event(
        tenant_id=tenant_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action="update",
        entity_type="tenant_profile",
        entity_id=tenant_id,
        field_name=",".join(allowed.keys()),
        new_value="updated",
        ip_address=ip_address,
        user_agent=user_agent,
        conn=conn,
    )
    return get_tenant_profile(tenant_id=tenant_id, conn=conn)


def list_employees(*, tenant_id: int, conn: Any, limit: int = 200) -> list[dict[str, Any]]:
    from modules.documents.service import fetch_document_categories_by_employee

    items = list_employee_summaries(tenant_id=tenant_id, conn=conn, limit=limit)
    profile = get_tenant_profile(tenant_id=tenant_id, conn=conn)
    payroll_enabled = bool(profile.get("payroll_enabled"))
    categories_by_employee = fetch_document_categories_by_employee(tenant_id=tenant_id, conn=conn)
    enriched = []
    for item in items:
        summary = list_completion_summary(
            item,
            payroll_enabled=payroll_enabled,
            document_categories=categories_by_employee.get(item["id"], []),
        )
        enriched.append({**item, **summary})
    return enriched


def create_employee(
    *,
    tenant_id: int,
    data: dict[str, Any],
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO employees (
              tenant_id, first_name, last_name, email, job_title, salary, work_location,
              start_date, status, is_sponsored, phone, department, employment_type
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING """
            + EMPLOYEE_COLUMNS,
            (
                tenant_id,
                data["first_name"],
                data["last_name"],
                data.get("email"),
                data.get("job_title"),
                data.get("salary"),
                data.get("work_location"),
                data.get("start_date"),
                data.get("status", "active"),
                data.get("is_sponsored", False),
                data.get("phone"),
                data.get("department"),
                data.get("employment_type", "full_time"),
            ),
        )
        row = cur.fetchone()
        conn.commit()
        emp = _row_to_employee(row)
    from modules.employees.service import after_employee_created

    after_employee_created(
        tenant_id=tenant_id,
        employee=emp,
        data=data,
        actor_username=actor_username,
        actor_role=actor_role,
        conn=conn,
    )
    log_employee_data_event(
        tenant_id=tenant_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action="create",
        entity_type="employee",
        entity_id=emp["id"],
        ip_address=ip_address,
        user_agent=user_agent,
        conn=conn,
    )
    return emp


def update_employee(
    *,
    tenant_id: int,
    employee_id: int,
    updates: dict[str, Any],
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> dict[str, Any]:
    allowed_keys = {
        "first_name",
        "last_name",
        "email",
        "job_title",
        "salary",
        "work_location",
        "start_date",
        "status",
        "is_sponsored",
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
    }
    status_reason = updates.pop("status_reason", None)
    allowed = {k: v for k, v in updates.items() if k in allowed_keys}
    if not allowed:
        return get_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn)

    from modules.employees.service import after_employee_updated, get_employee_row

    from modules.employees.repository import _row_to_employee, update_employee_fields

    old_row = get_employee_row(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    if not old_row:
        raise LookupError("employee not found")

    allowed = {k: v for k, v in updates.items() if k in allowed_keys}
    if not allowed:
        return get_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn)

    emp = update_employee_fields(
        tenant_id=tenant_id,
        employee_id=employee_id,
        updates=allowed,
        conn=conn,
    )
    new_row = get_employee_row(tenant_id=tenant_id, employee_id=employee_id, conn=conn)

    after_employee_updated(
        tenant_id=tenant_id,
        employee_id=employee_id,
        old_row=old_row,
        new_row=new_row or emp,
        actor_username=actor_username,
        actor_role=actor_role,
        conn=conn,
        reason=status_reason,
    )
    log_employee_data_event(
        tenant_id=tenant_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action="update",
        entity_type="employee",
        entity_id=employee_id,
        field_name=",".join(allowed.keys()),
        ip_address=ip_address,
        user_agent=user_agent,
        conn=conn,
    )
    return emp


def get_employee(*, tenant_id: int, employee_id: int, conn: Any) -> dict[str, Any]:
    employee = fetch_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    if not employee:
        raise LookupError("employee not found")
    return employee


def delete_employee(
    *,
    tenant_id: int,
    employee_id: int,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM employees WHERE tenant_id = %s AND id = %s RETURNING id",
            (tenant_id, employee_id),
        )
        row = cur.fetchone()
        if not row:
            raise LookupError("employee not found")
        conn.commit()
    log_employee_data_event(
        tenant_id=tenant_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action="delete",
        entity_type="employee",
        entity_id=employee_id,
        ip_address=ip_address,
        user_agent=user_agent,
        conn=conn,
    )


def list_documents(
    *,
    tenant_id: int,
    conn: Any,
    limit: int = 200,
    category: str | None = None,
    lifecycle_stage: str | None = None,
) -> list[dict[str, Any]]:
    from modules.documents.service import list_tenant_documents

    return list_tenant_documents(
        tenant_id=tenant_id,
        conn=conn,
        category=category,
        lifecycle_stage=lifecycle_stage,
        limit=limit,
    )


def create_document(
    *,
    tenant_id: int,
    data: dict[str, Any],
    uploaded_by: str,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> dict[str, Any]:
    from modules.documents.service import create_tenant_document

    doc = create_tenant_document(
        tenant_id=tenant_id,
        data=data,
        uploaded_by=uploaded_by,
        conn=conn,
    )
    log_employee_data_event(
        tenant_id=tenant_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action="create",
        entity_type="tenant_document",
        entity_id=doc["id"],
        ip_address=ip_address,
        user_agent=user_agent,
        conn=conn,
    )
    return doc


def update_document(
    *,
    tenant_id: int,
    document_id: int,
    updates: dict[str, Any],
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> dict[str, Any]:
    from modules.documents.service import update_tenant_document

    doc = update_tenant_document(
        tenant_id=tenant_id,
        document_id=document_id,
        updates=updates,
        conn=conn,
    )
    log_employee_data_event(
        tenant_id=tenant_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action="update",
        entity_type="tenant_document",
        entity_id=document_id,
        field_name=",".join(updates.keys()),
        ip_address=ip_address,
        user_agent=user_agent,
        conn=conn,
    )
    return doc


def delete_document(
    *,
    tenant_id: int,
    document_id: int,
    actor_username: str,
    actor_role: str,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> None:
    from modules.documents.service import delete_tenant_document

    delete_tenant_document(tenant_id=tenant_id, document_id=document_id, conn=conn)
    log_employee_data_event(
        tenant_id=tenant_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action="delete",
        entity_type="tenant_document",
        entity_id=document_id,
        ip_address=ip_address,
        user_agent=user_agent,
        conn=conn,
    )


def admin_overview(*, tenant_id: int, conn: Any) -> dict[str, Any]:
    from plan_features import effective_features_for_tenant
    from trial_service import trial_snapshot

    profile = get_tenant_profile(tenant_id=tenant_id, conn=conn)
    trial = trial_snapshot(tenant_id=tenant_id, conn=conn)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM employees WHERE tenant_id = %s AND status = 'active'",
            (tenant_id,),
        )
        active_employees = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM tenant_documents WHERE tenant_id = %s", (tenant_id,))
        document_count = int(cur.fetchone()[0])
        cur.execute(
            "SELECT COUNT(*) FROM employees WHERE tenant_id = %s AND is_sponsored = TRUE",
            (tenant_id,),
        )
        sponsored_employees = int(cur.fetchone()[0])

    plan_flags = effective_features_for_tenant(
        plan_id=profile["subscription_plan"],
        payroll_enabled=bool(profile["payroll_enabled"]),
        sponsored_employees=sponsored_employees,
        subscription_status=profile.get("subscription_status"),
        trial_access_allowed=bool(trial.get("access_allowed")),
    )
    return {
        "tenant_name": profile["name"],
        "subscription_plan": profile["subscription_plan"],
        "subscription_status": profile["subscription_status"],
        "max_employees": profile["max_employees"],
        "active_employees": active_employees,
        "document_count": document_count,
        "payroll_plan_id": profile["payroll_plan_id"],
        "trial_active": bool(plan_flags.get("trial_active")),
        "days_remaining": trial.get("days_remaining"),
        **plan_flags,
    }
