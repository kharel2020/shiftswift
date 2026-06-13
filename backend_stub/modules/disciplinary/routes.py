"""Disciplinary HTTP routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from auth_service import AuthUser
from config import load_settings
from core.database import get_connection
from core.permissions import check_permission
from deps import client_ip, get_hr_user, resolve_tenant_id
from modules.disciplinary import service as disciplinary_service

settings = load_settings()


def _require_disciplinary_plan(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> None:
    from admin_service import get_tenant_profile
    from plan_features import assert_tenant_feature

    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        assert_tenant_feature(tenant_id=tenant_id, feature="disciplinary", conn=conn)
    finally:
        conn.close()


router = APIRouter(
    prefix="/disciplinary",
    tags=["Disciplinary Case Management"],
    dependencies=[Depends(_require_disciplinary_plan)],
)


class CaseCreate(BaseModel):
    employee_id: int
    misconduct_type: str = Field(min_length=2, max_length=64)
    misconduct_type_other: str | None = Field(default=None, max_length=500)
    date_reported: date
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    linked_absence_context: str | None = Field(default=None, max_length=2000)
    assigned_investigator: str | None = Field(default=None, max_length=120)
    initial_note: str | None = Field(default=None, max_length=8000)


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    note_type: str = Field(default="investigation", pattern="^(investigation|hearing|appeal|system)$")


class CloseCaseRequest(BaseModel):
    close_outcome: str = Field(
        pattern="^(no_action|written_warning|final_warning|dismissal|withdrawn)$"
    )


@router.get("/investigators")
def list_investigators(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "disciplinary.read")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        items = disciplinary_service.list_investigators(tenant_id=tenant_id, conn=conn)
    finally:
        conn.close()
    return {"items": items}


@router.get("/cases/export")
def export_cases(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> Response:
    check_permission(current_user, "disciplinary.read")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        csv_data = disciplinary_service.export_cases_csv(tenant_id=tenant_id, conn=conn)
    finally:
        conn.close()
    filename = f"disciplinary-cases-{date.today().isoformat()}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cases")
def list_cases(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    status: str | None = None,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "disciplinary.read")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        items = disciplinary_service.list_cases(tenant_id=tenant_id, conn=conn, status=status)
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.post("/cases")
def create_case(
    payload: CaseCreate,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "disciplinary.write")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        return disciplinary_service.create_case(
            tenant_id=tenant_id,
            employee_id=payload.employee_id,
            misconduct_type=payload.misconduct_type,
            misconduct_type_other=payload.misconduct_type_other,
            date_reported=payload.date_reported,
            severity=payload.severity,
            linked_absence_context=payload.linked_absence_context,
            assigned_investigator=payload.assigned_investigator,
            initial_note=payload.initial_note,
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            conn=conn,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/cases/{case_id}")
def get_case(
    case_id: int,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "disciplinary.read")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        case = disciplinary_service.get_case(tenant_id=tenant_id, case_id=case_id, conn=conn)
        disciplinary_service._log_case_audit(
            conn=conn,
            tenant_id=tenant_id,
            case_id=case_id,
            action="view",
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
        )
        return case
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/cases/{case_id}/notes")
def list_notes(
    case_id: int,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "disciplinary.read")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        items = disciplinary_service.list_notes(
            tenant_id=tenant_id,
            case_id=case_id,
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.post("/cases/{case_id}/notes")
def add_note(
    case_id: int,
    payload: NoteCreate,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "disciplinary.write")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        return disciplinary_service.add_note(
            tenant_id=tenant_id,
            case_id=case_id,
            body=payload.body,
            note_type=payload.note_type,
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            conn=conn,
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/cases/{case_id}/close")
def close_case(
    case_id: int,
    payload: CloseCaseRequest,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "disciplinary.write")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        return disciplinary_service.close_case(
            tenant_id=tenant_id,
            case_id=case_id,
            close_outcome=payload.close_outcome,
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()
