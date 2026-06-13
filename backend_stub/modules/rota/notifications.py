"""Email staff when a rota week is published."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from core.notifications import send_email_content

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _looks_like_email(value: str | None) -> bool:
    return bool(value and _EMAIL_RE.match(str(value).strip()))


def _week_label(week_start: date) -> str:
    week_end = week_start + timedelta(days=6)
    start_fmt = week_start.strftime("%d %b")
    end_fmt = week_end.strftime("%d %b %Y")
    return f"{start_fmt} – {end_fmt}"


def _shift_summary_lines(shifts: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for shift in sorted(shifts, key=lambda item: (item.get("shift_date") or "", item.get("start_time") or "")):
        shift_date = date.fromisoformat(str(shift["shift_date"])[:10])
        day = DAY_LABELS[shift_date.weekday()]
        start = str(shift.get("start_time") or "")[:5]
        end = str(shift.get("end_time") or "")[:5]
        role = shift.get("role_label") or "Shift"
        lines.append(f"{day} {shift_date.strftime('%d %b')}: {start}–{end} ({role})")
    return lines


def notify_rota_published(
    *,
    tenant_id: int,
    week_start: date,
    shifts: list[dict[str, Any]],
    conn: Any,
) -> dict[str, int]:
    """Email each scheduled employee about their published shifts."""
    from admin_service import get_tenant_profile, tenant_notification_delivery_enabled
    from core.email_templates import rota_published_email

    if not tenant_notification_delivery_enabled(
        tenant_id=tenant_id,
        event_id="rota_published",
        conn=conn,
    ):
        return {"emails_sent": 0, "emails_skipped": len({s["employee_id"] for s in shifts})}

    profile = get_tenant_profile(tenant_id=tenant_id, conn=conn)
    if not profile.get("notify_on_rota_publish", True):
        return {"emails_sent": 0, "emails_skipped": len({s["employee_id"] for s in shifts})}

    tenant_name = profile.get("trading_name") or profile.get("name") or "Your employer"
    week_label = _week_label(week_start)

    shifts_by_employee: dict[int, list[dict[str, Any]]] = {}
    for shift in shifts:
        shifts_by_employee.setdefault(int(shift["employee_id"]), []).append(shift)

    employee_ids = list(shifts_by_employee.keys())
    if not employee_ids:
        return {"emails_sent": 0, "emails_skipped": 0}

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, first_name, last_name, email, email_notifications_enabled
            FROM employees
            WHERE tenant_id = %s AND id = ANY(%s)
            """,
            (tenant_id, employee_ids),
        )
        rows = {row[0]: row for row in cur.fetchall()}

    sent = skipped = 0
    for employee_id, employee_shifts in shifts_by_employee.items():
        row = rows.get(employee_id)
        if not row:
            skipped += 1
            continue
        if not row[4]:
            skipped += 1
            continue
        email = (row[3] or "").strip()
        if not _looks_like_email(email):
            skipped += 1
            continue

        employee_name = f"{row[1]} {row[2]}".strip() or "there"
        shift_lines = _shift_summary_lines(employee_shifts)
        content = rota_published_email(
            employee_name=employee_name,
            tenant_name=tenant_name,
            week_label=week_label,
            shift_lines=shift_lines,
        )
        send_email_content(
            conn=conn,
            tenant_id=tenant_id,
            content=content,
            purpose="employee",
            to=email,
            audience="employee",
            payload={
                "type": "rota_published",
                "employee_id": employee_id,
                "week_start": week_start.isoformat(),
            },
            deliver_now=True,
            commit=False,
        )
        sent += 1

    conn.commit()
    return {"emails_sent": sent, "emails_skipped": skipped}
