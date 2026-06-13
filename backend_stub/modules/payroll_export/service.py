"""CSV exports compatible with BrightPay / Xero employee import workflows."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from admin_service import list_employees

UK_TZ = ZoneInfo("Europe/London")

EMPLOYEE_CSV_COLUMNS = (
    "ShiftSwift Employee ID",
    "Forename",
    "Surname",
    "Email",
    "Phone",
    "NI Number",
    "Date of Birth",
    "Start Date",
    "Job Title",
    "Department",
    "Employment Type",
    "Annual Salary",
    "Status",
    "Home Address",
    "Work Location",
)

HOURS_CSV_COLUMNS = (
    "ShiftSwift Employee ID",
    "Forename",
    "Surname",
    "Punch Date",
    "Clock In",
    "Clock Out",
    "Hours Worked",
)


def _employee_row(emp: dict[str, Any]) -> list[str]:
    return [
        str(emp.get("id") or ""),
        str(emp.get("first_name") or ""),
        str(emp.get("last_name") or ""),
        str(emp.get("email") or ""),
        str(emp.get("phone") or ""),
        str(emp.get("ni_number") or ""),
        str(emp.get("date_of_birth") or ""),
        str(emp.get("start_date") or ""),
        str(emp.get("job_title") or ""),
        str(emp.get("department") or ""),
        str(emp.get("employment_type") or ""),
        "" if emp.get("salary") is None else f"{float(emp['salary']):.2f}",
        str(emp.get("status") or ""),
        str(emp.get("home_address") or ""),
        str(emp.get("work_location") or ""),
    ]


def build_employees_csv(*, tenant_id: int, conn: Any) -> str:
    employees = list_employees(tenant_id=tenant_id, conn=conn, limit=5000)
    active = [e for e in employees if e.get("status") in {"active", "onboarding", "suspended"}]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EMPLOYEE_CSV_COLUMNS)
    for emp in active:
        writer.writerow(_employee_row(emp))
    return buffer.getvalue()


def _pair_punch_hours(
    punches: list[tuple[Any, ...]],
) -> list[tuple[int, str, str, date, datetime | None, datetime | None, float | None]]:
    """Pair in/out punches per employee per day; return computed hours when possible."""
    by_emp_day: dict[tuple[int, date], list[tuple[str, datetime]]] = {}
    names: dict[int, tuple[str, str]] = {}
    for emp_id, first, last, punch_type, punched_at in punches:
        names[int(emp_id)] = (str(first or ""), str(last or ""))
        if not isinstance(punched_at, datetime):
            continue
        if punched_at.tzinfo is None:
            punched_at = punched_at.replace(tzinfo=timezone.utc)
        day = punched_at.astimezone(UK_TZ).date()
        by_emp_day.setdefault((int(emp_id), day), []).append((punch_type, punched_at))

    rows: list[tuple[int, str, str, date, datetime | None, datetime | None, float | None]] = []
    for (emp_id, day), events in sorted(by_emp_day.items()):
        events.sort(key=lambda item: item[1])
        first_name, last_name = names.get(emp_id, ("", ""))
        clock_in = next((ts for typ, ts in events if typ == "in"), None)
        clock_out = next((ts for typ, ts in reversed(events) if typ == "out"), None)
        hours = None
        if clock_in and clock_out and clock_out > clock_in:
            hours = round((clock_out - clock_in).total_seconds() / 3600, 2)
        rows.append((emp_id, first_name, last_name, day, clock_in, clock_out, hours))
    return rows


def _normalize_period(
    *,
    from_date: date | None,
    to_date: date | None,
) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    start = from_date or today.replace(day=1)
    end = to_date or today
    if end < start:
        start, end = end, start
    return start, end


def _fetch_punch_rows(
    *,
    tenant_id: int,
    conn: Any,
    from_date: date,
    to_date: date,
) -> list[tuple[Any, ...]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tp.employee_id, e.first_name, e.last_name, tp.punch_type, tp.punched_at
            FROM time_punches tp
            JOIN employees e ON e.id = tp.employee_id AND e.tenant_id = tp.tenant_id
            WHERE tp.tenant_id = %s
              AND tp.punched_at >= %s
              AND tp.punched_at < %s
            ORDER BY tp.employee_id, tp.punched_at
            """,
            (
                tenant_id,
                datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc),
                datetime.combine(to_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
            ),
        )
        return cur.fetchall()


def _format_clock_time(value: datetime | None) -> str:
    if not value:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(UK_TZ).strftime("%H:%M")


def build_hours_report(
    *,
    tenant_id: int,
    conn: Any,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, Any]:
    from admin_service import get_tenant_profile

    start, end = _normalize_period(from_date=from_date, to_date=to_date)
    profile = get_tenant_profile(tenant_id=tenant_id, conn=conn)
    tenant_name = str(profile.get("trading_name") or profile.get("name") or f"Tenant {tenant_id}")

    paired = _pair_punch_hours(_fetch_punch_rows(tenant_id=tenant_id, conn=conn, from_date=start, to_date=end))
    by_employee: dict[int, list[tuple[int, str, str, date, datetime | None, datetime | None, float | None]]] = {}
    for row in paired:
        by_employee.setdefault(row[0], []).append(row)

    employees: list[dict[str, Any]] = []
    grand_total_hours = 0.0
    for emp_id in sorted(by_employee):
        day_rows = by_employee[emp_id]
        first_name = day_rows[0][1] if day_rows else ""
        last_name = day_rows[0][2] if day_rows else ""
        detail_rows: list[dict[str, Any]] = []
        total_hours = 0.0
        days_worked = 0
        incomplete_days = 0
        for _, _, _, day, clock_in, clock_out, hours in day_rows:
            complete = hours is not None
            if complete:
                total_hours += hours
                days_worked += 1
            else:
                incomplete_days += 1
            detail_rows.append(
                {
                    "date": day.isoformat(),
                    "clock_in": _format_clock_time(clock_in),
                    "clock_out": _format_clock_time(clock_out),
                    "hours": hours,
                    "status": "complete" if complete else "incomplete",
                }
            )
        grand_total_hours += total_hours
        employees.append(
            {
                "employee_id": emp_id,
                "first_name": first_name,
                "last_name": last_name,
                "name": f"{first_name} {last_name}".strip(),
                "total_hours": round(total_hours, 2),
                "days_worked": days_worked,
                "incomplete_days": incomplete_days,
                "rows": detail_rows,
            }
        )

    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "generated_at": datetime.now(timezone.utc).astimezone(UK_TZ).strftime("%d %b %Y %H:%M %Z"),
        "timezone": "Europe/London",
        "methodology": (
            "Each row pairs the first clock-in and last clock-out on the same calendar day (UK time). "
            "Hours worked = clock out minus clock in. Rows marked incomplete are missing a punch pair "
            "and are excluded from employee totals."
        ),
        "employees": employees,
        "grand_total_hours": round(grand_total_hours, 2),
        "employee_count": len(employees),
    }


def build_hours_csv(
    *,
    tenant_id: int,
    conn: Any,
    from_date: date | None = None,
    to_date: date | None = None,
) -> str:
    start, end = _normalize_period(from_date=from_date, to_date=to_date)
    punch_rows = _fetch_punch_rows(tenant_id=tenant_id, conn=conn, from_date=start, to_date=end)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HOURS_CSV_COLUMNS)
    for emp_id, first, last, day, clock_in, clock_out, hours in _pair_punch_hours(punch_rows):
        writer.writerow(
            [
                str(emp_id),
                first,
                last,
                day.isoformat(),
                _format_clock_time(clock_in),
                _format_clock_time(clock_out),
                "" if hours is None else f"{hours:.2f}",
            ]
        )
    return buffer.getvalue()


def payroll_export_info() -> dict[str, object]:
    return {
        "message": "Download CSV files from ShiftSwift HR and import into BrightPay, Xero, or your accountant's tools.",
        "partners": [
            {
                "id": "brightpay",
                "name": "BrightPay",
                "url": "https://www.brightpay.co.uk/",
                "notes": "Import employees via CSV from Employer > Import/Export.",
            },
            {
                "id": "xero",
                "name": "Xero Payroll",
                "url": "https://www.xero.com/uk/payroll/",
                "notes": "Add employees manually or via CSV depending on your Xero setup.",
            },
        ],
        "exports": {
            "employees_csv": "/admin/payroll-export/employees.csv",
            "hours_csv": "/admin/payroll-export/hours.csv",
            "hours_pdf": "/admin/payroll-export/hours.pdf",
        },
        "employee_fields": list(EMPLOYEE_CSV_COLUMNS),
    }
