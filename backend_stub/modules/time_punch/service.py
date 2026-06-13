"""Time punch — geofence validation and punch records."""

from __future__ import annotations

import csv
import io
import math
import os
from datetime import date, datetime, timezone
from typing import Any, Literal

from modules.time_punch.geocode import geocode_address

PunchType = Literal["in", "out"]
DEFAULT_RADIUS_M = int(os.getenv("PUNCH_GEOFENCE_RADIUS_M", "150"))


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def resolve_employee(*, tenant_id: int, username: str, conn: Any) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, first_name, last_name, email, status
            FROM employees
            WHERE tenant_id = %s AND lower(email) = lower(%s)
            LIMIT 1
            """,
            (tenant_id, username),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "first_name": row[1],
        "last_name": row[2],
        "email": row[3],
        "status": row[4],
    }


def _site_row(row: tuple[Any, ...]) -> dict[str, Any]:
    updated_at = row[9] if len(row) > 9 else None
    permitted_roles = row[10] if len(row) > 10 else "all"
    return {
        "id": row[0],
        "tenant_id": row[1],
        "name": row[2],
        "address": row[3],
        "latitude": row[4],
        "longitude": row[5],
        "radius_meters": row[6],
        "is_primary": bool(row[7]),
        "is_active": bool(row[8]),
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
        "permitted_roles": permitted_roles or "all",
    }


def format_permitted_roles(value: str | None) -> str:
    if not value or value == "all":
        return "All staff"
    return value.replace(",", ", ")


def list_punch_sites(*, tenant_id: int, conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active, updated_at,
                   COALESCE(permitted_roles, 'all')
            FROM punch_sites
            WHERE tenant_id = %s
            ORDER BY is_primary DESC, name
            """,
            (tenant_id,),
        )
        return [_site_row(row) for row in cur.fetchall()]


def upsert_primary_punch_site(
    *,
    tenant_id: int,
    name: str,
    address: str,
    latitude: float,
    longitude: float,
    radius_meters: int = DEFAULT_RADIUS_M,
    conn: Any,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM punch_sites
            WHERE tenant_id = %s AND is_primary = TRUE
            LIMIT 1
            """,
            (tenant_id,),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """
                UPDATE punch_sites SET
                  name = %s,
                  address = %s,
                  latitude = %s,
                  longitude = %s,
                  radius_meters = %s,
                  is_active = TRUE,
                  updated_at = NOW()
                WHERE id = %s
                RETURNING id, tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active, updated_at,
                          COALESCE(permitted_roles, 'all')
                """,
                (name, address, latitude, longitude, radius_meters, existing[0]),
            )
        else:
            cur.execute(
                """
                INSERT INTO punch_sites (
                  tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, TRUE)
                RETURNING id, tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active, updated_at,
                          COALESCE(permitted_roles, 'all')
                """,
                (tenant_id, name, address, latitude, longitude, radius_meters),
            )
        row = cur.fetchone()
    conn.commit()
    return _site_row(row)


def sync_primary_site_from_tenant_address(*, tenant_id: int, conn: Any) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT name, trading_name, registered_address FROM tenants WHERE id = %s",
            (tenant_id,),
        )
        row = cur.fetchone()
    if not row or not row[2]:
        return None
    name = row[1] or row[0] or "Primary site"
    address = str(row[2]).strip()
    coords = geocode_address(address)
    if not coords:
        return None
    lat, lng = coords
    return upsert_primary_punch_site(
        tenant_id=tenant_id,
        name=f"{name} — main",
        address=address,
        latitude=lat,
        longitude=lng,
        conn=conn,
    )


def create_punch_site(
    *,
    tenant_id: int,
    name: str,
    address: str,
    radius_meters: int = DEFAULT_RADIUS_M,
    is_primary: bool = False,
    permitted_roles: str = "all",
    conn: Any,
) -> dict[str, Any]:
    clean_name = name.strip()
    clean_address = address.strip()
    if not clean_name or not clean_address:
        raise ValueError("Name and address are required")
    coords = geocode_address(clean_address)
    if not coords:
        raise LookupError("Could not geocode address — check the address or try a fuller postcode")
    lat, lng = coords
    roles = (permitted_roles or "all").strip() or "all"
    with conn.cursor() as cur:
        if is_primary:
            cur.execute(
                "UPDATE punch_sites SET is_primary = FALSE WHERE tenant_id = %s AND is_primary = TRUE",
                (tenant_id,),
            )
        cur.execute(
            """
            INSERT INTO punch_sites (
              tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active, permitted_roles
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s)
            RETURNING id, tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active, updated_at,
                      COALESCE(permitted_roles, 'all')
            """,
            (tenant_id, clean_name, clean_address, lat, lng, radius_meters, is_primary, roles),
        )
        row = cur.fetchone()
    conn.commit()
    return _site_row(row)


def assign_employee_to_site(
    *,
    tenant_id: int,
    employee_id: int,
    punch_site_id: int,
    conn: Any,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO employee_punch_assignments (tenant_id, employee_id, punch_site_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (employee_id, punch_site_id) DO NOTHING
            """,
            (tenant_id, employee_id, punch_site_id),
        )
    conn.commit()


def eligible_sites_for_employee(*, tenant_id: int, employee_id: int, conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ps.id, ps.tenant_id, ps.name, ps.address, ps.latitude, ps.longitude,
                   ps.radius_meters, ps.is_primary, ps.is_active
            FROM employee_punch_assignments epa
            JOIN punch_sites ps ON ps.id = epa.punch_site_id
            WHERE epa.tenant_id = %s AND epa.employee_id = %s AND ps.is_active = TRUE
            """,
            (tenant_id, employee_id),
        )
        assigned = [_site_row(row) for row in cur.fetchall()]
        if assigned:
            return assigned
        cur.execute(
            """
            SELECT id, tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active, updated_at
            FROM punch_sites
            WHERE tenant_id = %s AND is_active = TRUE
            ORDER BY is_primary DESC, id
            """,
            (tenant_id,),
        )
        return [_site_row(row) for row in cur.fetchall()]


def last_punch(*, tenant_id: int, employee_id: int, conn: Any) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tp.id, tp.punch_type, tp.punched_at, ps.name, tp.punch_site_id
            FROM time_punches tp
            JOIN punch_sites ps ON ps.id = tp.punch_site_id
            WHERE tp.tenant_id = %s AND tp.employee_id = %s
            ORDER BY tp.punched_at DESC
            LIMIT 1
            """,
            (tenant_id, employee_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    punched_at = row[2]
    return {
        "id": row[0],
        "punch_type": row[1],
        "punched_at": punched_at.isoformat() if isinstance(punched_at, datetime) else punched_at,
        "site_name": row[3],
        "punch_site_id": row[4],
    }


def employee_punch_status(*, tenant_id: int, employee_id: int, conn: Any) -> dict[str, Any]:
    from datetime import date

    from modules.rota.attendance import expected_shift_for_employee_on_date, list_employee_week_shifts
    from modules.rota.service import monday_on_or_before

    sites = eligible_sites_for_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    last = last_punch(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    clocked_in = bool(last and last["punch_type"] == "in")
    today = date.today()
    week_start = monday_on_or_before(today)
    expected_shift = expected_shift_for_employee_on_date(
        tenant_id=tenant_id,
        employee_id=employee_id,
        on_date=today,
        conn=conn,
    )
    week_shifts = list_employee_week_shifts(
        tenant_id=tenant_id,
        employee_id=employee_id,
        week_start=week_start,
        conn=conn,
    )
    return {
        "clocked_in": clocked_in,
        "last_punch": last,
        "assigned_sites": [
            {
                "id": s["id"],
                "name": s["name"],
                "address": s["address"],
                "radius_meters": s["radius_meters"],
            }
            for s in sites
        ],
        "expected_shift_today": expected_shift,
        "week_shifts": week_shifts,
        "week_start": week_start.isoformat(),
    }


def record_punch(
    *,
    tenant_id: int,
    employee_id: int,
    username: str,
    punch_type: PunchType,
    latitude: float,
    longitude: float,
    accuracy_meters: float | None,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> dict[str, Any]:
    employee = resolve_employee(tenant_id=tenant_id, username=username, conn=conn)
    if not employee or employee["id"] != employee_id:
        raise LookupError("employee not found")
    if employee["status"] not in {"active", "onboarding"}:
        raise PermissionError("employee is not active")

    last = last_punch(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    if punch_type == "in" and last and last["punch_type"] == "in":
        raise ValueError("Already clocked in — clock out first")
    if punch_type == "out" and (not last or last["punch_type"] != "in"):
        raise ValueError("Not clocked in")

    sites = eligible_sites_for_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    if not sites:
        raise LookupError("No punch sites configured for this business")

    best_site = None
    best_distance = None
    for site in sites:
        distance = haversine_meters(latitude, longitude, site["latitude"], site["longitude"])
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_site = site

    assert best_site is not None and best_distance is not None
    within = best_distance <= float(best_site["radius_meters"])
    if not within:
        raise PermissionError(
            f"You must be within {best_site['radius_meters']}m of {best_site['name']} to punch "
            f"(currently ~{int(best_distance)}m away)"
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO time_punches (
              tenant_id, employee_id, punch_site_id, punch_type, punched_at,
              latitude, longitude, accuracy_meters, distance_meters, within_geofence,
              app_username, ip_address, user_agent
            )
            VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s, TRUE, %s, %s, %s)
            RETURNING id, punched_at
            """,
            (
                tenant_id,
                employee_id,
                best_site["id"],
                punch_type,
                latitude,
                longitude,
                accuracy_meters,
                best_distance,
                username,
                ip_address,
                user_agent,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    punched_at = row[1]
    return {
        "id": row[0],
        "punch_type": punch_type,
        "punched_at": punched_at.isoformat() if isinstance(punched_at, datetime) else punched_at,
        "site_name": best_site["name"],
        "distance_meters": round(best_distance, 1),
        "clocked_in": punch_type == "in",
    }


def record_admin_punch(
    *,
    tenant_id: int,
    employee_id: int,
    punch_site_id: int,
    punch_type: PunchType,
    punched_at: datetime | None,
    admin_note: str | None,
    recorded_by: str,
    conn: Any,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, first_name, last_name, status FROM employees
            WHERE id = %s AND tenant_id = %s
            """,
            (employee_id, tenant_id),
        )
        employee = cur.fetchone()
        if not employee:
            raise LookupError("Employee not found")
        if employee[3] not in {"active", "onboarding"}:
            raise PermissionError("Employee is not active")

        cur.execute(
            """
            SELECT id, tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active, updated_at
            FROM punch_sites
            WHERE id = %s AND tenant_id = %s AND is_active = TRUE
            """,
            (punch_site_id, tenant_id),
        )
        site_row = cur.fetchone()
        if not site_row:
            raise LookupError("Punch site not found")
        site = _site_row(site_row)

        ts = punched_at or datetime.now(timezone.utc)
        if punched_at and punched_at.tzinfo is None:
            ts = punched_at.replace(tzinfo=timezone.utc)

        cur.execute(
            """
            INSERT INTO time_punches (
              tenant_id, employee_id, punch_site_id, punch_type, punched_at,
              latitude, longitude, accuracy_meters, distance_meters, within_geofence,
              app_username, admin_override, admin_note, recorded_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, 0, TRUE, %s, TRUE, %s, %s)
            RETURNING id, punched_at
            """,
            (
                tenant_id,
                employee_id,
                punch_site_id,
                punch_type,
                ts,
                site["latitude"],
                site["longitude"],
                recorded_by,
                admin_note,
                recorded_by,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    punched_at_out = row[1]
    return {
        "id": row[0],
        "punch_type": punch_type,
        "punched_at": punched_at_out.isoformat() if isinstance(punched_at_out, datetime) else punched_at_out,
        "site_name": site["name"],
        "employee_name": f"{employee[1]} {employee[2]}".strip(),
        "admin_override": True,
    }


def _punch_row(row: tuple[Any, ...]) -> dict[str, Any]:
    punched_at = row[2]
    radius_meters = int(row[11]) if len(row) > 11 and row[11] is not None else None
    within_geofence = bool(row[12]) if len(row) > 12 else True
    distance = float(row[3]) if row[3] is not None else None
    if distance is not None and radius_meters is not None and not bool(row[8] if len(row) > 8 else False):
        within_geofence = distance <= radius_meters
    return {
        "id": row[0],
        "punch_type": row[1],
        "punched_at": punched_at.isoformat() if isinstance(punched_at, datetime) else punched_at,
        "distance_meters": distance,
        "employee_name": f"{row[4]} {row[5]}".strip(),
        "employee_email": row[6],
        "site_name": row[7],
        "admin_override": bool(row[8]) if len(row) > 8 else False,
        "admin_note": row[9] if len(row) > 9 else None,
        "punch_site_id": row[10] if len(row) > 10 else None,
        "radius_meters": radius_meters,
        "within_geofence": within_geofence,
    }


def list_recent_punches(
    *,
    tenant_id: int,
    conn: Any,
    limit: int = 100,
    employee_id: int | None = None,
    punch_site_id: int | None = None,
    punch_type: PunchType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, Any]]:
    clauses = ["tp.tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if employee_id is not None:
        clauses.append("tp.employee_id = %s")
        params.append(employee_id)
    if punch_site_id is not None:
        clauses.append("tp.punch_site_id = %s")
        params.append(punch_site_id)
    if punch_type is not None:
        clauses.append("tp.punch_type = %s")
        params.append(punch_type)
    if date_from is not None:
        clauses.append("tp.punched_at >= %s::date")
        params.append(date_from.isoformat())
    if date_to is not None:
        clauses.append("tp.punched_at < (%s::date + INTERVAL '1 day')")
        params.append(date_to.isoformat())
    where = " AND ".join(clauses)
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT tp.id, tp.punch_type, tp.punched_at, tp.distance_meters,
                   e.first_name, e.last_name, e.email, ps.name,
                   COALESCE(tp.admin_override, FALSE), tp.admin_note,
                   tp.punch_site_id, ps.radius_meters, tp.within_geofence
            FROM time_punches tp
            JOIN employees e ON e.id = tp.employee_id
            JOIN punch_sites ps ON ps.id = tp.punch_site_id
            WHERE {where}
            ORDER BY tp.punched_at DESC
            LIMIT %s
            """,
            params,
        )
        rows = cur.fetchall()
    return [_punch_row(row) for row in rows]


def export_punches_csv(
    *,
    tenant_id: int,
    conn: Any,
    limit: int = 5000,
    employee_id: int | None = None,
    punch_site_id: int | None = None,
    punch_type: PunchType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> str:
    items = list_recent_punches(
        tenant_id=tenant_id,
        conn=conn,
        limit=limit,
        employee_id=employee_id,
        punch_site_id=punch_site_id,
        punch_type=punch_type,
        date_from=date_from,
        date_to=date_to,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Punched at",
            "Employee",
            "Email",
            "Type",
            "Site",
            "Distance (m)",
            "Admin override",
            "Admin note",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item.get("punched_at") or "",
                item.get("employee_name") or "",
                item.get("employee_email") or "",
                "Clock in" if item.get("punch_type") == "in" else "Clock out",
                item.get("site_name") or "",
                item.get("distance_meters") if item.get("distance_meters") is not None else "",
                "Yes" if item.get("admin_override") else "No",
                item.get("admin_note") or "",
            ]
        )
    return buffer.getvalue()
