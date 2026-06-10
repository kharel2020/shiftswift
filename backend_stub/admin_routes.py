"""Admin workspace API — shared metadata, tenant profile, employees, documents."""

from __future__ import annotations

import os
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from modules.documents.constants import DOCUMENT_LIFECYCLE_STAGES
from modules.employees.constants import (
    EMPLOYEE_DOCUMENT_CATEGORIES,
    EMPLOYMENT_TYPES,
    RTW_STATUSES,
    SECTION_BRANCHES as EMPLOYEE_SECTION_BRANCHES,
    SECTION_DESCRIPTIONS as EMPLOYEE_SECTION_DESCRIPTIONS,
    SECTION_LABELS as EMPLOYEE_SECTION_LABELS,
    SECTION_ORDER as EMPLOYEE_SECTION_ORDER,
    SECTION_STEPS as EMPLOYEE_SECTION_STEPS,
    WORKER_TYPES,
)
from modules.recruitment.constants import (
    HIRING_DECISIONS,
    OFFER_STATUSES,
    POSTING_PLATFORMS,
    SECTION_BRANCHES as RECRUITMENT_SECTION_BRANCHES,
    SECTION_DESCRIPTIONS as RECRUITMENT_SECTION_DESCRIPTIONS,
    SECTION_LABELS as RECRUITMENT_SECTION_LABELS,
    SECTION_ORDER as RECRUITMENT_SECTION_ORDER,
    SECTION_STEPS as RECRUITMENT_SECTION_STEPS,
)
from admin_service import (
    ADVERT_PLATFORMS,
    DOCUMENT_CATEGORIES,
    EMPLOYEE_STATUSES,
    admin_overview,
    create_document,
    create_employee,
    delete_document,
    delete_employee,
    get_tenant_profile,
    list_documents,
    list_employees,
    update_document,
    update_employee,
    update_tenant_profile,
)
from auth_service import AuthUser
from billing_plans import list_plans
from billing_promotions import list_discount_codes, list_referral_codes
from partner_commission_service import (
    build_introducer_commission_csv,
    fetch_introducer_commission_rows,
    introducer_export_filename,
)
from payroll_plans import list_payroll_plans
from contracts_service import TEMPLATE_REGISTRY
from deps import client_ip, get_admin_user, get_hr_user, require_tenant_subscription, resolve_tenant_id
from config import load_settings
from sponsor_licence_compliance import absence_type_catalog
from brand import brand_payload

router = APIRouter(
    prefix="/admin",
    tags=["Admin Workspace"],
    dependencies=[Depends(require_tenant_subscription)],
)
settings = load_settings()


def _db_conn() -> Any:
    import psycopg2

    url = os.getenv("DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
    return psycopg2.connect(url)


class TenantProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    trading_name: str | None = Field(default=None, max_length=200)
    company_number: str | None = Field(default=None, max_length=32)
    registered_address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=32)
    billing_email: str | None = Field(default=None, max_length=254)
    vat_number: str | None = Field(default=None, max_length=32)
    signatory_name: str | None = Field(default=None, max_length=120)
    signatory_title: str | None = Field(default=None, max_length=120)
    signatory_email: str | None = Field(default=None, max_length=254)


class EmployeeCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr | None = None
    job_title: str | None = Field(default=None, max_length=120)
    salary: float | None = Field(default=None, ge=0)
    work_location: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    status: str = Field(
        default="active",
        pattern="^(active|inactive|onboarding|suspended|terminated)$",
    )
    is_sponsored: bool = False
    visa_type: str | None = Field(default=None, max_length=80)
    visa_expiry_date: date | None = None
    share_code: str | None = Field(default=None, max_length=32)


class EmployeeUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    email: EmailStr | None = None
    job_title: str | None = Field(default=None, max_length=120)
    salary: float | None = Field(default=None, ge=0)
    work_location: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    status: str | None = Field(
        default=None,
        pattern="^(active|inactive|onboarding|suspended|terminated)$",
    )
    is_sponsored: bool | None = None
    status_reason: str | None = Field(default=None, max_length=500)


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(default="general", max_length=64)
    lifecycle_stage: str = Field(default="general", max_length=64)
    document_url: str | None = Field(default=None, max_length=2048)
    notes: str | None = Field(default=None, max_length=4000)
    expires_at: date | None = None
    original_filename: str | None = Field(default=None, max_length=255)
    employee_id: int | None = None


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=64)
    lifecycle_stage: str | None = Field(default=None, max_length=64)
    document_url: str | None = Field(default=None, max_length=2048)
    notes: str | None = Field(default=None, max_length=4000)
    expires_at: date | None = None
    original_filename: str | None = Field(default=None, max_length=255)
    employee_id: int | None = None


@router.get("/metadata")
def admin_metadata() -> dict[str, object]:
    platform_plans = [
        {"value": p.id, "label": f"{p.name} — £{p.price_gbp_ex_vat:.2f}/mo ex VAT"}
        for p in list_plans()
    ]
    payroll_plans = [
        {"value": p.id, "label": f"{p.name} — £{p.price_gbp_ex_vat:.2f}/mo ex VAT"}
        for p in list_payroll_plans()
    ]
    templates = [
        {"value": tid, "label": meta["name"]}
        for tid, meta in TEMPLATE_REGISTRY.items()
    ]
    templates.append({"value": "pack", "label": "Full pack (MSA + DPA + Order)"})
    return {
        "brand": brand_payload(),
        "advert_platforms": ADVERT_PLATFORMS,
        "document_categories": DOCUMENT_CATEGORIES,
        "document_lifecycle_stages": DOCUMENT_LIFECYCLE_STAGES,
        "employee_statuses": EMPLOYEE_STATUSES,
        "employment_types": EMPLOYMENT_TYPES,
        "worker_types": WORKER_TYPES,
        "employee_sections": [
            {
                "value": key,
                "step": EMPLOYEE_SECTION_STEPS[key],
                "label": EMPLOYEE_SECTION_LABELS[key],
                "description": EMPLOYEE_SECTION_DESCRIPTIONS[key],
                "branch": EMPLOYEE_SECTION_BRANCHES.get(key),
            }
            for key in EMPLOYEE_SECTION_ORDER
        ],
        "employee_lifecycle": [
            {
                "value": key,
                "step": EMPLOYEE_SECTION_STEPS[key],
                "label": EMPLOYEE_SECTION_LABELS[key],
                "description": EMPLOYEE_SECTION_DESCRIPTIONS[key],
            }
            for key in EMPLOYEE_SECTION_ORDER
        ],
        "recruitment_pipeline": [
            {
                "value": key,
                "step": RECRUITMENT_SECTION_STEPS[key],
                "label": RECRUITMENT_SECTION_LABELS[key],
                "description": RECRUITMENT_SECTION_DESCRIPTIONS[key],
                "branch": RECRUITMENT_SECTION_BRANCHES.get(key),
            }
            for key in RECRUITMENT_SECTION_ORDER
        ],
        "recruitment_posting_platforms": POSTING_PLATFORMS,
        "hiring_decisions": HIRING_DECISIONS,
        "offer_statuses": OFFER_STATUSES,
        "employee_document_categories": EMPLOYEE_DOCUMENT_CATEGORIES,
        "rtw_statuses": RTW_STATUSES,
        "absence_excuse_types": [
            {"value": item["value"], "label": item["label"]}
            for item in absence_type_catalog()
        ],
        "platform_plans": platform_plans,
        "payroll_plans": payroll_plans,
        "contract_templates": templates,
    }


@router.get("/overview")
def get_overview(
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        return admin_overview(tenant_id=tenant_id, conn=conn)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/tenant-profile")
def read_tenant_profile(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        return get_tenant_profile(tenant_id=tenant_id, conn=conn)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.patch("/tenant-profile")
def patch_tenant_profile(
    payload: TenantProfileUpdate,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    updates = payload.model_dump(exclude_unset=True)
    updates = {key: (None if value == "" else value) for key, value in updates.items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    conn = _db_conn()
    try:
        return update_tenant_profile(
            tenant_id=tenant_id,
            updates=updates,
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/employees")
def read_employees(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        items = list_employees(tenant_id=tenant_id, conn=conn)
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.post("/employees")
def add_employee(
    payload: EmployeeCreate,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        return create_employee(
            tenant_id=tenant_id,
            data=payload.model_dump(),
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
    finally:
        conn.close()


@router.patch("/employees/{employee_id}")
def patch_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    conn = _db_conn()
    try:
        return update_employee(
            tenant_id=tenant_id,
            employee_id=employee_id,
            updates=updates,
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.delete("/employees/{employee_id}")
def remove_employee(
    employee_id: int,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, str]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        delete_employee(
            tenant_id=tenant_id,
            employee_id=employee_id,
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()
    return {"status": "deleted"}


@router.get("/documents")
def read_documents(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    category: str | None = None,
    lifecycle_stage: str | None = None,
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        items = list_documents(
            tenant_id=tenant_id,
            conn=conn,
            category=category,
            lifecycle_stage=lifecycle_stage,
        )
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.post("/documents")
def add_document(
    payload: DocumentCreate,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        return create_document(
            tenant_id=tenant_id,
            data=payload.model_dump(),
            uploaded_by=current_user.username,
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.patch("/documents/{document_id}")
def patch_document(
    document_id: int,
    payload: DocumentUpdate,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        return update_document(
            tenant_id=tenant_id,
            document_id=document_id,
            updates=updates,
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.delete("/documents/{document_id}")
def remove_document(
    document_id: int,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, str]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        delete_document(
            tenant_id=tenant_id,
            document_id=document_id,
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()
    return {"status": "deleted"}


@router.get("/billing/discount-codes")
def read_discount_codes(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
) -> dict[str, object]:
    conn = _db_conn()
    try:
        items = list_discount_codes(conn=conn)
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.get("/billing/referral-codes")
def read_referral_codes(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
) -> dict[str, object]:
    conn = _db_conn()
    try:
        items = list_referral_codes(conn=conn)
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.get("/billing/introducer-commission.csv")
def export_introducer_commission_csv(
    current_user: Annotated[AuthUser, Depends(get_admin_user)],
    referral_code: str | None = None,
):
    """Platform admin only — estimated introducer commissions for manual payout."""
    from fastapi.responses import Response

    conn = _db_conn()
    try:
        rows = fetch_introducer_commission_rows(conn=conn, referral_code=referral_code)
    finally:
        conn.close()
    csv_body = build_introducer_commission_csv(rows)
    filename = introducer_export_filename(referral_code=referral_code)
    return Response(
        content=csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/payroll-export/info")
def payroll_export_metadata() -> dict[str, object]:
    from modules.payroll_export.service import payroll_export_info

    return payroll_export_info()


@router.get("/payroll-export/employees.csv")
def payroll_export_employees_csv(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    from fastapi.responses import Response

    from modules.payroll_export.service import build_employees_csv

    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        csv_body = build_employees_csv(tenant_id=tenant_id, conn=conn)
    finally:
        conn.close()
    filename = f"shiftswift-employees-tenant-{tenant_id}.csv"
    return Response(
        content=csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/payroll-export/hours.csv")
def payroll_export_hours_csv(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    from_date: date | None = None,
    to_date: date | None = None,
):
    from fastapi.responses import Response

    from modules.payroll_export.service import build_hours_csv

    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        csv_body = build_hours_csv(
            tenant_id=tenant_id,
            conn=conn,
            from_date=from_date,
            to_date=to_date,
        )
    finally:
        conn.close()
    filename = f"shiftswift-hours-tenant-{tenant_id}.csv"
    return Response(
        content=csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
