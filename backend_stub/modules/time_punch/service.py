"""Time punch — geofence validation and punch records."""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
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
    }


def list_punch_sites(*, tenant_id: int, conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active
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
                RETURNING id, tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active
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
                RETURNING id, tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active
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
            SELECT id, tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active
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
    sites = eligible_sites_for_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    last = last_punch(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    clocked_in = bool(last and last["punch_type"] == "in")
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


def list_recent_punches(*, tenant_id: int, conn: Any, limit: int = 100) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tp.id, tp.punch_type, tp.punched_at, tp.distance_meters,
                   e.first_name, e.last_name, e.email, ps.name
            FROM time_punches tp
            JOIN employees e ON e.id = tp.employee_id
            JOIN punch_sites ps ON ps.id = tp.punch_site_id
            WHERE tp.tenant_id = %s
            ORDER BY tp.punched_at DESC
            LIMIT %s
            """,
            (tenant_id, limit),
        )
        rows = cur.fetchall()
    items = []
    for row in rows:
        punched_at = row[2]
        items.append(
            {
                "id": row[0],
                "punch_type": row[1],
                "punched_at": punched_at.isoformat() if isinstance(punched_at, datetime) else punched_at,
                "distance_meters": float(row[3]) if row[3] is not None else None,
                "employee_name": f"{row[4]} {row[5]}".strip(),
                "employee_email": row[6],
                "site_name": row[7],
            }
        )
    return items
