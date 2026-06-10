"""Rota week and shift CRUD with validation and optimistic locking."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

MIN_SHIFT_MINUTES = 15
MAX_SHIFT_HOURS = 16
BILLABLE_EMPLOYEE_STATUSES = frozenset({"active", "onboarding", "suspended"})


class RotaValidationError(ValueError):
    """Raised when shift data fails validation."""

    def __init__(self, message: str, *, field: str | None = None, index: int | None = None) -> None:
        super().__init__(message)
        self.field = field
        self.index = index


class RotaConflictError(ValueError):
    """Raised when optimistic lock version does not match."""

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(f"Rota was updated elsewhere (expected version {expected}, now {actual}). Reload and try again.")
        self.expected = expected
        self.actual = actual


def parse_week_start(value: str | date) -> date:
    if isinstance(value, date):
        week_start = value
    else:
        week_start = date.fromisoformat(str(value).strip()[:10])
    if week_start.weekday() != 0:
        raise RotaValidationError("week_start must be a Monday (ISO week)", field="week_start")
    return week_start


def monday_on_or_before(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_dates(week_start: date) -> list[date]:
    return [week_start + timedelta(days=offset) for offset in range(7)]


def shift_window(*, shift_date: date, start_time: time, end_time: time) -> tuple[datetime, datetime]:
    start = datetime.combine(shift_date, start_time, tzinfo=timezone.utc)
    if end_time <= start_time:
        end = datetime.combine(shift_date + timedelta(days=1), end_time, tzinfo=timezone.utc)
    else:
        end = datetime.combine(shift_date, end_time, tzinfo=timezone.utc)
    return start, end


def shifts_overlap(
    a_date: date,
    a_start: time,
    a_end: time,
    b_date: date,
    b_start: time,
    b_end: time,
) -> bool:
    a0, a1 = shift_window(shift_date=a_date, start_time=a_start, end_time=a_end)
    b0, b1 = shift_window(shift_date=b_date, start_time=b_start, end_time=b_end)
    return a0 < b1 and b0 < a1


def _shift_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "employee_id": row[1],
        "shift_date": row[2].isoformat(),
        "start_time": row[3].strftime("%H:%M"),
        "end_time": row[4].strftime("%H:%M"),
        "role_label": row[5] or "",
        "notes": row[6] or "",
        "employee_name": row[7],
        "employee_status": row[8],
    }


def _week_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "week_start": row[1].isoformat(),
        "status": row[2],
        "version": row[3],
        "published_at": row[4].isoformat() if row[4] else None,
        "updated_at": row[5].isoformat() if row[5] else None,
    }


def _load_active_employee_ids(*, tenant_id: int, conn: Any) -> set[int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM employees
            WHERE tenant_id = %s AND status IN ('active', 'onboarding', 'suspended')
            """,
            (tenant_id,),
        )
        return {int(row[0]) for row in cur.fetchall()}


def validate_shift_payload(
    *,
    shift: dict[str, Any],
    week_start: date,
    week_end: date,
    active_employee_ids: set[int],
    index: int,
) -> dict[str, Any]:
    try:
        employee_id = int(shift["employee_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RotaValidationError("employee_id is required", field="employee_id", index=index) from exc

    if employee_id not in active_employee_ids:
        raise RotaValidationError("Employee not found or not active for rota", field="employee_id", index=index)

    try:
        shift_date = date.fromisoformat(str(shift["shift_date"])[:10])
    except (TypeError, ValueError) as exc:
        raise RotaValidationError("shift_date must be YYYY-MM-DD", field="shift_date", index=index) from exc

    if shift_date < week_start or shift_date > week_end:
        raise RotaValidationError("shift_date must fall within the selected week", field="shift_date", index=index)

    try:
        start_time = time.fromisoformat(str(shift["start_time"])[:5])
        end_time = time.fromisoformat(str(shift["end_time"])[:5])
    except (TypeError, ValueError) as exc:
        raise RotaValidationError("start_time and end_time must be HH:MM", field="start_time", index=index) from exc

    if start_time == end_time:
        raise RotaValidationError("Shift start and end cannot be the same", field="end_time", index=index)

    start_dt, end_dt = shift_window(shift_date=shift_date, start_time=start_time, end_time=end_time)
    duration_minutes = (end_dt - start_dt).total_seconds() / 60
    if duration_minutes < MIN_SHIFT_MINUTES:
        raise RotaValidationError(f"Shift must be at least {MIN_SHIFT_MINUTES} minutes", field="end_time", index=index)
    if duration_minutes > MAX_SHIFT_HOURS * 60:
        raise RotaValidationError(f"Shift cannot exceed {MAX_SHIFT_HOURS} hours", field="end_time", index=index)

    role_label = str(shift.get("role_label") or "").strip()[:80]
    notes = str(shift.get("notes") or "").strip()[:500]
    shift_id = shift.get("id")
    parsed_id = int(shift_id) if shift_id not in (None, "") else None

    return {
        "id": parsed_id,
        "employee_id": employee_id,
        "shift_date": shift_date,
        "start_time": start_time,
        "end_time": end_time,
        "role_label": role_label,
        "notes": notes,
    }


def validate_no_overlaps(shifts: list[dict[str, Any]]) -> None:
    for i, left in enumerate(shifts):
        for j in range(i + 1, len(shifts)):
            right = shifts[j]
            if left["employee_id"] != right["employee_id"]:
                continue
            if shifts_overlap(
                left["shift_date"],
                left["start_time"],
                left["end_time"],
                right["shift_date"],
                right["start_time"],
                right["end_time"],
            ):
                raise RotaValidationError(
                    "Overlapping shifts for the same employee",
                    field="start_time",
                    index=j,
                )


def get_or_create_week(
    *,
    tenant_id: int,
    week_start: date,
    actor_username: str,
    conn: Any,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, week_start, status, version, published_at, updated_at
            FROM rota_weeks
            WHERE tenant_id = %s AND week_start = %s
            """,
            (tenant_id, week_start),
        )
        row = cur.fetchone()
        if row:
            return _week_row(row)

        cur.execute(
            """
            INSERT INTO rota_weeks (tenant_id, week_start, created_by, updated_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id, week_start, status, version, published_at, updated_at
            """,
            (tenant_id, week_start, actor_username, actor_username),
        )
        return _week_row(cur.fetchone())


def list_shifts_for_week(*, tenant_id: int, week_start: date, conn: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, week_start, status, version, published_at, updated_at
            FROM rota_weeks
            WHERE tenant_id = %s AND week_start = %s
            """,
            (tenant_id, week_start),
        )
        week_row = cur.fetchone()
        if not week_row:
            return None, []

        week = _week_row(week_row)
        cur.execute(
            """
            SELECT s.id, s.employee_id, s.shift_date, s.start_time, s.end_time,
                   s.role_label, s.notes,
                   trim(both ' ' from coalesce(e.first_name, '') || ' ' || coalesce(e.last_name, '')) AS employee_name,
                   e.status
            FROM rota_shifts s
            JOIN employees e ON e.id = s.employee_id AND e.tenant_id = s.tenant_id
            WHERE s.tenant_id = %s AND s.rota_week_id = %s
            ORDER BY s.shift_date, s.start_time, employee_name
            """,
            (tenant_id, week["id"]),
        )
        shifts = [_shift_row(row) for row in cur.fetchall()]
        return week, shifts


def get_week_rota(*, tenant_id: int, week_start: date, conn: Any) -> dict[str, Any]:
    week, shifts = list_shifts_for_week(tenant_id=tenant_id, week_start=week_start, conn=conn)
    return {
        "week_start": week_start.isoformat(),
        "week_end": (week_start + timedelta(days=6)).isoformat(),
        "week_days": [day.isoformat() for day in week_dates(week_start)],
        "week": week,
        "shifts": shifts,
    }


def save_week_shifts(
    *,
    tenant_id: int,
    week_start: date,
    shifts_payload: list[dict[str, Any]],
    expected_version: int | None,
    actor_username: str,
    conn: Any,
) -> dict[str, Any]:
    week_end = week_start + timedelta(days=6)
    active_ids = _load_active_employee_ids(tenant_id=tenant_id, conn=conn)
    parsed = [
        validate_shift_payload(
            shift=item,
            week_start=week_start,
            week_end=week_end,
            active_employee_ids=active_ids,
            index=index,
        )
        for index, item in enumerate(shifts_payload)
    ]
    validate_no_overlaps(parsed)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, status, version
            FROM rota_weeks
            WHERE tenant_id = %s AND week_start = %s
            FOR UPDATE
            """,
            (tenant_id, week_start),
        )
        row = cur.fetchone()
        if row:
            week_id, status, version = row[0], row[1], int(row[2])
            if expected_version is not None and expected_version != version:
                raise RotaConflictError(expected_version, version)
        else:
            cur.execute(
                """
                INSERT INTO rota_weeks (tenant_id, week_start, created_by, updated_by)
                VALUES (%s, %s, %s, %s)
                RETURNING id, status, version
                """,
                (tenant_id, week_start, actor_username, actor_username),
            )
            week_id, status, version = cur.fetchone()

        cur.execute("DELETE FROM rota_shifts WHERE tenant_id = %s AND rota_week_id = %s", (tenant_id, week_id))

        for shift in parsed:
            cur.execute(
                """
                INSERT INTO rota_shifts (
                  tenant_id, rota_week_id, employee_id, shift_date,
                  start_time, end_time, role_label, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    week_id,
                    shift["employee_id"],
                    shift["shift_date"],
                    shift["start_time"],
                    shift["end_time"],
                    shift["role_label"],
                    shift["notes"],
                ),
            )

        cur.execute(
            """
            UPDATE rota_weeks
            SET version = version + 1,
                status = 'draft',
                published_at = NULL,
                updated_by = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, week_start, status, version, published_at, updated_at
            """,
            (actor_username, week_id),
        )
        week = _week_row(cur.fetchone())

    conn.commit()
    _, shifts = list_shifts_for_week(tenant_id=tenant_id, week_start=week_start, conn=conn)
    return {
        "week": week,
        "shifts": shifts,
        "message": "Rota saved",
    }


def publish_week(
    *,
    tenant_id: int,
    week_start: date,
    expected_version: int,
    actor_username: str,
    conn: Any,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, version
            FROM rota_weeks
            WHERE tenant_id = %s AND week_start = %s
            FOR UPDATE
            """,
            (tenant_id, week_start),
        )
        row = cur.fetchone()
        if not row:
            raise RotaValidationError("No rota for this week — save shifts first", field="week_start")
        week_id, version = row[0], int(row[1])
        if version != expected_version:
            raise RotaConflictError(expected_version, version)

        cur.execute(
            "SELECT COUNT(*) FROM rota_shifts WHERE tenant_id = %s AND rota_week_id = %s",
            (tenant_id, week_id),
        )
        if int(cur.fetchone()[0]) == 0:
            raise RotaValidationError("Add at least one shift before publishing", field="shifts")

        cur.execute(
            """
            UPDATE rota_weeks
            SET status = 'published',
                published_at = NOW(),
                version = version + 1,
                updated_by = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, week_start, status, version, published_at, updated_at
            """,
            (actor_username, week_id),
        )
        week = _week_row(cur.fetchone())

    conn.commit()
    _, shifts = list_shifts_for_week(tenant_id=tenant_id, week_start=week_start, conn=conn)
    return {"week": week, "shifts": shifts, "message": "Rota published"}
