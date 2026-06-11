"""Rota routes — admin planning and employee self-service."""

from __future__ import annotations

from typing import Annotated

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from auth_service import AuthUser
from config import load_settings
from core.database import get_connection
from core.permissions import check_permission
from deps import get_employee_user, get_hr_user, require_tenant_subscription, resolve_tenant_id
from modules.rota import attendance as rota_attendance
from modules.rota import requests as rota_requests
from modules.rota import service as rota_service
from modules.rota.service import RotaConflictError, RotaValidationError
from modules.time_punch import service as punch_service

settings = load_settings()

admin_router = APIRouter(
    prefix="/admin/rota",
    tags=["Rota admin"],
    dependencies=[Depends(require_tenant_subscription)],
)

employee_router = APIRouter(
    prefix="/rota",
    tags=["Rota employee"],
    dependencies=[Depends(require_tenant_subscription)],
)


class ShiftInput(BaseModel):
    id: int | None = None
    employee_id: int
    shift_date: str = Field(min_length=10, max_length=10)
    start_time: str = Field(min_length=4, max_length=5)
    end_time: str = Field(min_length=4, max_length=5)
    role_label: str = Field(default="", max_length=80)
    notes: str = Field(default="", max_length=500)


class SaveRotaRequest(BaseModel):
    shifts: list[ShiftInput] = Field(default_factory=list)
    expected_version: int | None = Field(default=None, ge=1)


class PublishRotaRequest(BaseModel):
    expected_version: int = Field(ge=1)


class CopyWeekRequest(BaseModel):
    expected_version: int | None = Field(default=None, ge=1)


class ReviewRequestBody(BaseModel):
    approve: bool


class EmployeeShiftRequestBody(BaseModel):
    request_type: str = Field(pattern="^(cover|swap)$")
    target_employee_id: int | None = None
    target_shift_id: int | None = None
    note: str = Field(default="", max_length=500)


def _handle_rota_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, RotaConflictError):
        return HTTPException(
            status_code=409,
            detail={"message": str(exc), "code": "version_conflict", "actual_version": exc.actual},
        )
    if isinstance(exc, RotaValidationError):
        return HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                "code": "validation_error",
                "field": exc.field,
                "index": exc.index,
            },
        )
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc


def _employee_for_user(*, tenant_id: int, user: AuthUser, conn) -> dict:
    employee = punch_service.resolve_employee(tenant_id=tenant_id, username=user.username, conn=conn)
    if not employee:
        raise HTTPException(status_code=404, detail="No employee record linked to this login")
    return employee


@admin_router.get("/weeks/{week_start}")
def get_week_rota(
    week_start: str,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    include_attendance: bool = Query(default=True),
) -> dict[str, object]:
    check_permission(current_user, "employees.read")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    try:
        parsed = rota_service.parse_week_start(week_start)
    except RotaValidationError as exc:
        raise _handle_rota_errors(exc) from exc

    conn = get_connection()
    try:
        rota_service.get_or_create_week(
            tenant_id=tenant_id,
            week_start=parsed,
            actor_username=current_user.username,
            conn=conn,
        )
        conn.commit()
        payload = rota_service.get_week_rota(tenant_id=tenant_id, week_start=parsed, conn=conn)
        if include_attendance and payload.get("shifts"):
            payload["attendance"] = rota_attendance.build_week_attendance(
                tenant_id=tenant_id,
                week_start=parsed,
                shifts=payload["shifts"],
                conn=conn,
            )
        return payload
    finally:
        conn.close()


@admin_router.get("/weeks/{week_start}/attendance")
def get_week_attendance(
    week_start: str,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "employees.read")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    parsed = rota_service.parse_week_start(week_start)
    conn = get_connection()
    try:
        _, shifts = rota_service.list_shifts_for_week(tenant_id=tenant_id, week_start=parsed, conn=conn)
        return rota_attendance.build_week_attendance(
            tenant_id=tenant_id,
            week_start=parsed,
            shifts=shifts,
            conn=conn,
        )
    finally:
        conn.close()


@admin_router.put("/weeks/{week_start}")
def save_week_rota(
    week_start: str,
    payload: SaveRotaRequest,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "employees.write")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    try:
        parsed = rota_service.parse_week_start(week_start)
        conn = get_connection()
        try:
            return rota_service.save_week_shifts(
                tenant_id=tenant_id,
                week_start=parsed,
                shifts_payload=[item.model_dump() for item in payload.shifts],
                expected_version=payload.expected_version,
                actor_username=current_user.username,
                conn=conn,
            )
        finally:
            conn.close()
    except (RotaValidationError, RotaConflictError, ValueError) as exc:
        raise _handle_rota_errors(exc) from exc


@admin_router.post("/weeks/{week_start}/copy-previous")
def copy_previous_week(
    week_start: str,
    payload: CopyWeekRequest,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "employees.write")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    try:
        parsed = rota_service.parse_week_start(week_start)
        conn = get_connection()
        try:
            return rota_service.copy_week_from_previous(
                tenant_id=tenant_id,
                week_start=parsed,
                expected_version=payload.expected_version,
                actor_username=current_user.username,
                conn=conn,
            )
        finally:
            conn.close()
    except (RotaValidationError, RotaConflictError, ValueError) as exc:
        raise _handle_rota_errors(exc) from exc


@admin_router.post("/weeks/{week_start}/publish")
def publish_week_rota(
    week_start: str,
    payload: PublishRotaRequest,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "employees.write")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    try:
        parsed = rota_service.parse_week_start(week_start)
        conn = get_connection()
        try:
            return rota_service.publish_week(
                tenant_id=tenant_id,
                week_start=parsed,
                expected_version=payload.expected_version,
                actor_username=current_user.username,
                conn=conn,
            )
        finally:
            conn.close()
    except (RotaValidationError, RotaConflictError, ValueError) as exc:
        raise _handle_rota_errors(exc) from exc


@admin_router.get("/shift-requests")
def list_admin_shift_requests(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    status: str | None = Query(default="pending"),
) -> dict[str, object]:
    check_permission(current_user, "employees.read")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        items = rota_requests.list_shift_requests(
            tenant_id=tenant_id,
            conn=conn,
            status=status if status in {"pending", "approved", "rejected", "cancelled"} else None,
        )
        return {"items": items}
    finally:
        conn.close()


@admin_router.post("/shift-requests/{request_id}/review")
def review_shift_request_route(
    request_id: int,
    payload: ReviewRequestBody,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "employees.write")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        return rota_requests.review_shift_request(
            tenant_id=tenant_id,
            request_id=request_id,
            approve=payload.approve,
            actor_username=current_user.username,
            conn=conn,
        )
    except RotaValidationError as exc:
        raise _handle_rota_errors(exc) from exc
    finally:
        conn.close()


@employee_router.get("/my-shifts")
def my_shifts(
    current_user: Annotated[AuthUser, Depends(get_employee_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    week_start: str | None = Query(default=None),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        employee = _employee_for_user(tenant_id=tenant_id, user=current_user, conn=conn)
        if week_start:
            parsed = rota_service.parse_week_start(week_start)
        else:
            parsed = rota_service.monday_on_or_before(date.today())
        shifts = rota_attendance.list_employee_week_shifts(
            tenant_id=tenant_id,
            employee_id=employee["id"],
            week_start=parsed,
            conn=conn,
        )
        return {
            "week_start": parsed.isoformat(),
            "week_end": (parsed + timedelta(days=6)).isoformat(),
            "shifts": shifts,
        }
    except RotaValidationError as exc:
        raise _handle_rota_errors(exc) from exc
    finally:
        conn.close()


@employee_router.post("/shifts/{shift_id}/requests")
def create_my_shift_request(
    shift_id: int,
    payload: EmployeeShiftRequestBody,
    current_user: Annotated[AuthUser, Depends(get_employee_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        employee = _employee_for_user(tenant_id=tenant_id, user=current_user, conn=conn)
        return rota_requests.create_shift_request(
            tenant_id=tenant_id,
            shift_id=shift_id,
            requester_employee_id=employee["id"],
            request_type=payload.request_type,  # type: ignore[arg-type]
            target_employee_id=payload.target_employee_id,
            target_shift_id=payload.target_shift_id,
            note=payload.note,
            conn=conn,
        )
    except RotaValidationError as exc:
        raise _handle_rota_errors(exc) from exc
    finally:
        conn.close()
