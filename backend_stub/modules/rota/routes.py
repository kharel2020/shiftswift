"""Admin rota routes — weekly shift planning."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from auth_service import AuthUser
from config import load_settings
from core.database import get_connection
from core.permissions import check_permission
from deps import get_hr_user, require_tenant_subscription, resolve_tenant_id
from modules.rota import service as rota_service
from modules.rota.service import RotaConflictError, RotaValidationError

settings = load_settings()

router = APIRouter(
    prefix="/admin/rota",
    tags=["Rota"],
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


@router.get("/weeks/{week_start}")
def get_week_rota(
    week_start: str,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
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
        return rota_service.get_week_rota(tenant_id=tenant_id, week_start=parsed, conn=conn)
    finally:
        conn.close()


@router.put("/weeks/{week_start}")
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


@router.post("/weeks/{week_start}/publish")
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
