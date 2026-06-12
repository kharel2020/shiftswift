"""Recruitment pipeline HTTP routes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from auth_service import AuthUser
from config import load_settings
from core.database import get_connection
from deps import client_ip, get_hr_user, require_tenant_subscription, resolve_tenant_id
from modules.recruitment.constants import LINK_ONLY_SECTIONS, SECTION_ORDER
from modules.recruitment.repository import create_vacancy, fetch_vacancy, list_vacancies
from modules.recruitment.workspace import (
    accept_offer_and_start_onboarding,
    build_workspace,
    fetch_advert_counts_by_vacancy,
    list_vacancy_completion_summary,
    patch_section,
)

router = APIRouter(
    prefix="/admin/recruitment",
    tags=["Recruitment"],
    dependencies=[Depends(require_tenant_subscription)],
)
settings = load_settings()

VALID_SECTIONS = frozenset(SECTION_ORDER) - LINK_ONLY_SECTIONS - {"offer_accepted"}


class VacancyCreate(BaseModel):
    job_title: str = Field(min_length=1, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=200)
    reference: str | None = Field(default=None, max_length=64)
    worker_type: str = Field(default="standard", pattern="^(standard|sponsored)$")


class SectionPatch(BaseModel):
    reference: str | None = Field(default=None, max_length=64)
    job_title: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=200)
    worker_type: str | None = Field(default=None, pattern="^(standard|sponsored)$")
    job_description: str | None = Field(default=None, max_length=8000)
    required_skills: str | None = Field(default=None, max_length=4000)
    salary_range_min: float | None = Field(default=None, ge=0)
    salary_range_max: float | None = Field(default=None, ge=0)
    candidate_name: str | None = Field(default=None, max_length=160)
    candidate_email: EmailStr | None = None
    candidate_phone: str | None = Field(default=None, max_length=32)
    candidate_cv_url: str | None = Field(default=None, max_length=2048)
    application_source: str | None = Field(default=None, max_length=120)
    screening_keywords: str | None = Field(default=None, max_length=2000)
    knockout_questions: str | None = Field(default=None, max_length=4000)
    pipeline_notes: str | None = Field(default=None, max_length=4000)
    candidate_rating: int | None = Field(default=None, ge=1, le=5)
    interview_at: datetime | None = None
    interview_video_link: str | None = Field(default=None, max_length=2048)
    scorecard_notes: str | None = Field(default=None, max_length=4000)
    hiring_decision: str | None = Field(default=None, pattern="^(pending|hire|reject)$")
    rejection_reason: str | None = Field(default=None, max_length=500)
    offer_letter_url: str | None = Field(default=None, max_length=2048)
    offer_status: str | None = Field(default=None, pattern="^(draft|sent|accepted|rejected)$")


@router.get("/vacancies")
def read_vacancies(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        items = list_vacancies(tenant_id=tenant_id, conn=conn)
        advert_counts = fetch_advert_counts_by_vacancy(tenant_id=tenant_id, conn=conn)
        enriched = []
        for item in items:
            summary = list_vacancy_completion_summary(
                item,
                advert_count=advert_counts.get(item["id"], 0),
            )
            enriched.append({**item, **summary})
    finally:
        conn.close()
    return {"items": enriched, "count": len(enriched)}


@router.post("/vacancies")
def add_vacancy(
    payload: VacancyCreate,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        return create_vacancy(tenant_id=tenant_id, data=payload.model_dump(), conn=conn)
    finally:
        conn.close()


@router.post("/vacancies/{vacancy_id}/close")
def close_vacancy(
    vacancy_id: int,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    from modules.recruitment.repository import update_vacancy_fields

    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        return update_vacancy_fields(
            tenant_id=tenant_id,
            vacancy_id=vacancy_id,
            updates={"status": "closed"},
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/vacancies/{vacancy_id}/workspace")
def read_vacancy_workspace(
    vacancy_id: int,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        return build_workspace(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.patch("/vacancies/{vacancy_id}/sections/{section}")
def patch_vacancy_section(
    vacancy_id: int,
    section: str,
    payload: SectionPatch,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    if section not in VALID_SECTIONS:
        raise HTTPException(status_code=404, detail="unknown section")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        return patch_section(
            tenant_id=tenant_id,
            vacancy_id=vacancy_id,
            section=section,
            updates=updates,
            actor_username=current_user.username,
            actor_role=current_user.role,
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/vacancies/{vacancy_id}/accept-offer")
def accept_offer(
    vacancy_id: int,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        return accept_offer_and_start_onboarding(
            tenant_id=tenant_id,
            vacancy_id=vacancy_id,
            actor_username=current_user.username,
            actor_role=current_user.role,
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()
