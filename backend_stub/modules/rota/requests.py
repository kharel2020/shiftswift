"""Shift cover and swap request workflow."""

from __future__ import annotations

from typing import Any, Literal

from modules.rota.service import RotaValidationError

RequestType = Literal["cover", "swap"]
RequestStatus = Literal["pending", "approved", "rejected", "cancelled"]


def _request_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "rota_shift_id": row[1],
        "request_type": row[2],
        "requester_employee_id": row[3],
        "target_employee_id": row[4],
        "target_shift_id": row[5],
        "note": row[6] or "",
        "status": row[7],
        "reviewed_by": row[8],
        "reviewed_at": row[9].isoformat() if row[9] else None,
        "created_at": row[10].isoformat() if row[10] else None,
        "shift_date": row[11].isoformat() if row[11] else None,
        "start_time": row[12].strftime("%H:%M") if row[12] else None,
        "end_time": row[13].strftime("%H:%M") if row[13] else None,
        "requester_name": row[14],
    }


def create_shift_request(
    *,
    tenant_id: int,
    shift_id: int,
    requester_employee_id: int,
    request_type: RequestType,
    target_employee_id: int | None,
    target_shift_id: int | None,
    note: str,
    conn: Any,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, s.employee_id, s.shift_date, s.start_time, s.end_time, w.status
            FROM rota_shifts s
            JOIN rota_weeks w ON w.id = s.rota_week_id
            WHERE s.id = %s AND s.tenant_id = %s
            """,
            (shift_id, tenant_id),
        )
        shift = cur.fetchone()
        if not shift:
            raise RotaValidationError("Shift not found", field="rota_shift_id")
        if shift[5] != "published":
            raise RotaValidationError("Shift requests require a published rota", field="rota_shift_id")
        if int(shift[1]) != requester_employee_id:
            raise RotaValidationError("You can only request changes to your own shifts", field="rota_shift_id")

        if request_type == "cover":
            if not target_employee_id:
                raise RotaValidationError("Cover request needs a colleague employee_id", field="target_employee_id")
        if request_type == "swap":
            if not target_shift_id:
                raise RotaValidationError("Swap request needs target_shift_id", field="target_shift_id")
            cur.execute(
                """
                SELECT id, employee_id FROM rota_shifts
                WHERE id = %s AND tenant_id = %s
                """,
                (target_shift_id, tenant_id),
            )
            target = cur.fetchone()
            if not target:
                raise RotaValidationError("Target shift not found", field="target_shift_id")
            target_employee_id = int(target[1])

        cur.execute(
            """
            INSERT INTO rota_shift_requests (
              tenant_id, rota_shift_id, request_type, requester_employee_id,
              target_employee_id, target_shift_id, note
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                tenant_id,
                shift_id,
                request_type,
                requester_employee_id,
                target_employee_id,
                target_shift_id,
                note[:500],
            ),
        )
        request_id = int(cur.fetchone()[0])
    conn.commit()
    items = list_shift_requests(tenant_id=tenant_id, conn=conn, request_id=request_id)
    return items[0]


def list_shift_requests(
    *,
    tenant_id: int,
    conn: Any,
    status: RequestStatus | None = None,
    request_id: int | None = None,
) -> list[dict[str, Any]]:
    clauses = ["r.tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if status:
        clauses.append("r.status = %s")
        params.append(status)
    if request_id:
        clauses.append("r.id = %s")
        params.append(request_id)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT r.id, r.rota_shift_id, r.request_type, r.requester_employee_id,
                   r.target_employee_id, r.target_shift_id, r.note, r.status,
                   r.reviewed_by, r.reviewed_at, r.created_at,
                   s.shift_date, s.start_time, s.end_time,
                   trim(both ' ' from coalesce(e.first_name, '') || ' ' || coalesce(e.last_name, ''))
            FROM rota_shift_requests r
            JOIN rota_shifts s ON s.id = r.rota_shift_id
            JOIN employees e ON e.id = r.requester_employee_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.created_at DESC
            """,
            tuple(params),
        )
        return [_request_row(row) for row in cur.fetchall()]


def review_shift_request(
    *,
    tenant_id: int,
    request_id: int,
    approve: bool,
    actor_username: str,
    conn: Any,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, rota_shift_id, request_type, requester_employee_id,
                   target_employee_id, target_shift_id, status
            FROM rota_shift_requests
            WHERE id = %s AND tenant_id = %s
            FOR UPDATE
            """,
            (request_id, tenant_id),
        )
        row = cur.fetchone()
        if not row:
            raise RotaValidationError("Request not found")
        if row[6] != "pending":
            raise RotaValidationError("Request is no longer pending")

        if not approve:
            cur.execute(
                """
                UPDATE rota_shift_requests
                SET status = 'rejected', reviewed_by = %s, reviewed_at = NOW(), updated_at = NOW()
                WHERE id = %s
                """,
                (actor_username, request_id),
            )
            conn.commit()
            return list_shift_requests(tenant_id=tenant_id, conn=conn, request_id=request_id)[0]

        request_type = row[2]
        shift_id = int(row[1])
        requester_id = int(row[3])
        target_employee_id = int(row[4]) if row[4] else None
        target_shift_id = int(row[5]) if row[5] else None

        if request_type == "cover":
            cur.execute(
                "UPDATE rota_shifts SET employee_id = %s, updated_at = NOW() WHERE id = %s AND tenant_id = %s",
                (target_employee_id, shift_id, tenant_id),
            )
        elif request_type == "swap":
            cur.execute(
                "SELECT employee_id, shift_date, start_time, end_time FROM rota_shifts WHERE id = %s AND tenant_id = %s",
                (target_shift_id, tenant_id),
            )
            target_row = cur.fetchone()
            if not target_row:
                raise RotaValidationError("Target shift missing")
            cur.execute(
                "UPDATE rota_shifts SET employee_id = %s, updated_at = NOW() WHERE id = %s AND tenant_id = %s",
                (target_row[0], shift_id, tenant_id),
            )
            cur.execute(
                "UPDATE rota_shifts SET employee_id = %s, updated_at = NOW() WHERE id = %s AND tenant_id = %s",
                (requester_id, target_shift_id, tenant_id),
            )

        cur.execute(
            """
            UPDATE rota_shift_requests
            SET status = 'approved', reviewed_by = %s, reviewed_at = NOW(), updated_at = NOW()
            WHERE id = %s
            """,
            (actor_username, request_id),
        )
    conn.commit()
    return list_shift_requests(tenant_id=tenant_id, conn=conn, request_id=request_id)[0]
