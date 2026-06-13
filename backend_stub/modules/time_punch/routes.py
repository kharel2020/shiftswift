"""Time punch HTTP routes — employee clock in/out and HR site management."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth_service import AuthUser
from config import load_settings
from core.database import get_connection
from deps import client_ip, get_employee_user, get_hr_user, require_tenant_subscription, resolve_tenant_id
from modules.time_punch import service as punch_service

settings = load_settings()

employee_router = APIRouter(prefix="/time-punch", tags=["Time punch"])
admin_router = APIRouter(
    prefix="/admin/time-punch",
    tags=["Time punch admin"],
    dependencies=[Depends(require_tenant_subscription)],
)


class PunchRequest(BaseModel):
    punch_type: Literal["in", "out"]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0)


class PunchSiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    radius_meters: int | None = Field(default=None, ge=25, le=2000)
    is_active: bool | None = None
    permitted_roles: str | None = Field(default=None, max_length=200)


class PunchSiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=3, max_length=500)
    radius_meters: int = Field(default=150, ge=25, le=2000)
    is_primary: bool = False
    permitted_roles: str = Field(default="all", max_length=200)


class AdminPunchRequest(BaseModel):
    employee_id: int
    punch_site_id: int
    punch_type: Literal["in", "out"]
    punched_at: str | None = None
    admin_note: str | None = Field(default=None, max_length=500)


def _parse_optional_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} — use YYYY-MM-DD") from exc


def _punch_filters(
    *,
    employee_id: int | None = None,
    site_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    punch_type: Literal["in", "out"] | None = None,
) -> dict[str, Any]:
    return {
        "employee_id": employee_id,
        "punch_site_id": site_id,
        "date_from": _parse_optional_date(date_from, "date_from"),
        "date_to": _parse_optional_date(date_to, "date_to"),
        "punch_type": punch_type,
    }


def _employee_for_user(*, tenant_id: int, user: AuthUser, conn: Any) -> dict[str, Any]:
    employee = punch_service.resolve_employee(tenant_id=tenant_id, username=user.username, conn=conn)
    if not employee:
        raise HTTPException(
            status_code=404,
            detail="No employee record linked to this login — ask HR to add your email to the employee register.",
        )
    return employee


@employee_router.get("/status")
def punch_status(
    current_user: Annotated[AuthUser, Depends(get_employee_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        employee = _employee_for_user(tenant_id=tenant_id, user=current_user, conn=conn)
        return punch_service.employee_punch_status(
            tenant_id=tenant_id,
            employee_id=employee["id"],
            conn=conn,
        )
    finally:
        conn.close()


@employee_router.post("/punch")
def punch(
    payload: PunchRequest,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_employee_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        employee = _employee_for_user(tenant_id=tenant_id, user=current_user, conn=conn)
        return punch_service.record_punch(
            tenant_id=tenant_id,
            employee_id=employee["id"],
            username=current_user.username,
            punch_type=payload.punch_type,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy_meters=payload.accuracy_meters,
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@admin_router.get("/sites")
def list_sites(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        items = punch_service.list_punch_sites(tenant_id=tenant_id, conn=conn)
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@admin_router.post("/sites/sync-from-address")
def sync_site_from_address(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        site = punch_service.sync_primary_site_from_tenant_address(tenant_id=tenant_id, conn=conn)
    finally:
        conn.close()
    if not site:
        raise HTTPException(
            status_code=400,
            detail="Could not sync punch site — set a registered business address first or check geocoding.",
        )
    return site


@admin_router.post("/sites")
def create_site(
    payload: PunchSiteCreate,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        return punch_service.create_punch_site(
            tenant_id=tenant_id,
            name=payload.name,
            address=payload.address,
            radius_meters=payload.radius_meters,
            is_primary=payload.is_primary,
            permitted_roles=payload.permitted_roles,
            conn=conn,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@admin_router.patch("/sites/{site_id}")
def patch_site(
    site_id: int,
    payload: PunchSiteUpdate,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    conn = get_connection()
    try:
        sets = ", ".join(f"{key} = %s" for key in updates)
        values = list(updates.values()) + [site_id, tenant_id]
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE punch_sites SET {sets}, updated_at = NOW()
                WHERE id = %s AND tenant_id = %s
                RETURNING id, tenant_id, name, address, latitude, longitude, radius_meters, is_primary, is_active, updated_at,
                          COALESCE(permitted_roles, 'all')
                """,
                values,
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Punch site not found")
        conn.commit()
        return punch_service._site_row(row)
    finally:
        conn.close()


@admin_router.get("/punches")
def list_punches(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    limit: int = 100,
    employee_id: int | None = None,
    site_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    punch_type: Literal["in", "out"] | None = None,
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    filters = _punch_filters(
        employee_id=employee_id,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
        punch_type=punch_type,
    )
    conn = get_connection()
    try:
        items = punch_service.list_recent_punches(
            tenant_id=tenant_id,
            conn=conn,
            limit=min(limit, 500),
            **filters,
        )
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@admin_router.get("/punches/export.csv")
def export_punches_csv(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    employee_id: int | None = None,
    site_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    punch_type: Literal["in", "out"] | None = None,
) -> Response:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    filters = _punch_filters(
        employee_id=employee_id,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
        punch_type=punch_type,
    )
    conn = get_connection()
    try:
        csv_data = punch_service.export_punches_csv(tenant_id=tenant_id, conn=conn, **filters)
    finally:
        conn.close()
    filename = f"time-punches-{date.today().isoformat()}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@admin_router.post("/punches/admin")
def admin_punch(
    payload: AdminPunchRequest,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    punched_at = None
    if payload.punched_at:
        try:
            punched_at = datetime.fromisoformat(payload.punched_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid punched_at timestamp") from exc
    conn = get_connection()
    try:
        return punch_service.record_admin_punch(
            tenant_id=tenant_id,
            employee_id=payload.employee_id,
            punch_site_id=payload.punch_site_id,
            punch_type=payload.punch_type,
            punched_at=punched_at,
            admin_note=payload.admin_note,
            recorded_by=current_user.username,
            conn=conn,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()
