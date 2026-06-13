"""Employee document share notifications."""

from __future__ import annotations

import re
from typing import Any

from core.notifications import send_email_content

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _looks_like_email(value: str | None) -> bool:
    return bool(value and _EMAIL_RE.match(str(value).strip()))


def notify_employee_document_shared(
    *,
    tenant_id: int,
    employee: dict[str, Any],
    document_title: str,
    category: str,
    category_label: str,
    pay_period: str | None,
    conn: Any,
    commit: bool = True,
) -> bool:
    """Email the employee when HR shares a document. Returns True if sent."""
    if not employee.get("email_notifications_enabled", True):
        return False
    email = employee.get("email")
    if not _looks_like_email(email):
        return False

    from admin_service import get_tenant_profile
    from core.email_templates import employee_document_shared_email

    profile = get_tenant_profile(tenant_id=tenant_id, conn=conn)
    tenant_name = profile.get("trading_name") or profile.get("name") or "Your employer"
    employee_name = f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip() or "there"

    content = employee_document_shared_email(
        employee_name=employee_name,
        document_title=document_title,
        category_label=category_label,
        pay_period=pay_period if category == "payslip" else None,
        tenant_name=tenant_name,
    )
    send_email_content(
        conn=conn,
        tenant_id=tenant_id,
        content=content,
        purpose="employee",
        to=str(email),
        audience="employee",
        payload={
            "type": "employee_document_shared",
            "employee_id": employee.get("id"),
            "document_title": document_title,
            "category": category,
        },
        deliver_now=True,
        commit=commit,
    )
    return True
