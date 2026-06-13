"""Send monthly working-hours PDF reports to payroll accountants."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, timedelta
from typing import Any

from core.notifications import send_email_content
from modules.payroll_export.hours_pdf import hours_report_pdf_bytes
from modules.payroll_export.service import build_hours_report

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _previous_calendar_month(as_of: date) -> tuple[date, date]:
    if as_of.month == 1:
        year, month = as_of.year - 1, 12
    else:
        year, month = as_of.year, as_of.month - 1
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def _already_sent(*, tenant_id: int, period_start: date, period_end: date, conn: Any) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM payroll_hours_report_log
            WHERE tenant_id = %s AND period_start = %s AND period_end = %s
            LIMIT 1
            """,
            (tenant_id, period_start, period_end),
        )
        return cur.fetchone() is not None


def send_payroll_hours_report(
    *,
    settings: Any,
    tenant_id: int,
    recipient_email: str,
    period_start: date,
    period_end: date,
    conn: Any,
    cc_hr_email: str | None = None,
    allow_resend: bool = False,
) -> dict[str, Any]:
    from admin_service import get_tenant_profile
    from core.email_templates import payroll_hours_report_email

    email = recipient_email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValueError("Enter a valid accountant or payroll bureau email address.")

    if not allow_resend and _already_sent(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        conn=conn,
    ):
        raise ValueError("This report was already sent for that period.")

    profile = get_tenant_profile(tenant_id=tenant_id, conn=conn)
    tenant_name = str(profile.get("trading_name") or profile.get("name") or f"Tenant {tenant_id}")
    report = build_hours_report(
        tenant_id=tenant_id,
        conn=conn,
        from_date=period_start,
        to_date=period_end,
    )
    pdf_bytes = hours_report_pdf_bytes(
        tenant_id=tenant_id,
        conn=conn,
        from_date=period_start,
        to_date=period_end,
    )
    filename = f"working-hours-{period_start.isoformat()}-to-{period_end.isoformat}.pdf"
    content = payroll_hours_report_email(
        tenant_name=tenant_name,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        employee_count=int(report["employee_count"]),
        total_hours=float(report["grand_total_hours"]),
        methodology=str(report["methodology"]),
    )
    payload = {
        "attachments": [
            {
                "filename": filename,
                "content_base64": __import__("base64").b64encode(pdf_bytes).decode("ascii"),
                "content_type": "application/pdf",
            }
        ],
    }
    if cc_hr_email and _EMAIL_RE.match(cc_hr_email.strip()):
        payload["cc"] = cc_hr_email.strip().lower()

    send_email_content(
        conn=conn,
        tenant_id=tenant_id,
        content=content,
        purpose="payroll_hours_report",
        to=email,
        audience="hr",
        payload=payload,
        deliver_now=True,
        commit=False,
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO payroll_hours_report_log (
              tenant_id, period_start, period_end, recipient_email, employee_count, total_hours
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, period_start, period_end) DO UPDATE SET
              recipient_email = EXCLUDED.recipient_email,
              employee_count = EXCLUDED.employee_count,
              total_hours = EXCLUDED.total_hours,
              sent_at = NOW()
            """,
            (
                tenant_id,
                period_start,
                period_end,
                email,
                int(report["employee_count"]),
                float(report["grand_total_hours"]),
            ),
        )
    conn.commit()
    return {
        "recipient_email": email,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "employee_count": report["employee_count"],
        "total_hours": report["grand_total_hours"],
    }


def process_monthly_payroll_hours_reports(*, settings: Any, conn: Any, as_of: date | None = None) -> dict[str, int]:
    """On the 1st of each month, email previous month's hours PDF to configured accountants."""
    today = as_of or date.today()
    summary = {"tenants_checked": 0, "reports_sent": 0, "skipped": 0}
    if today.day != 1:
        return summary

    period_start, period_end = _previous_calendar_month(today)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, payroll_accountant_email, billing_email
            FROM tenants
            WHERE payroll_hours_report_enabled = TRUE
              AND payroll_accountant_email IS NOT NULL
              AND trim(payroll_accountant_email) <> ''
            ORDER BY id
            """
        )
        rows = cur.fetchall()

    for tenant_id, accountant_email, billing_email in rows:
        summary["tenants_checked"] += 1
        if _already_sent(
            tenant_id=int(tenant_id),
            period_start=period_start,
            period_end=period_end,
            conn=conn,
        ):
            summary["skipped"] += 1
            continue
        try:
            send_payroll_hours_report(
                settings=settings,
                tenant_id=int(tenant_id),
                recipient_email=str(accountant_email),
                period_start=period_start,
                period_end=period_end,
                conn=conn,
                cc_hr_email=str(billing_email) if billing_email else None,
            )
            summary["reports_sent"] += 1
        except Exception as exc:
            conn.rollback()
            print(
                __import__("json").dumps(
                    {
                        "warning": "payroll_hours_report_failed",
                        "tenant_id": tenant_id,
                        "error": str(exc)[:300],
                    }
                )
            )
    return summary
