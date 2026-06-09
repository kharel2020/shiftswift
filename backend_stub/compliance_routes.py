"""FastAPI routes for UK Sponsor Licence mandatory safeguards."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from config import load_settings
from deps import AuthUser, get_hr_user, resolve_tenant_id
from sponsor_licence_compliance import (
    UK_RTW_CHECKLIST_URL,
    absence_type_catalog,
    add_advertisement_link,
    compliance_dashboard,
    create_advertisement_record,
    delete_sponsored_absence_day,
    evaluate_day9_absence_alerts,
    get_absence_streak_summaries,
    get_advertisement_record,
    list_advertisement_records,
    list_sponsored_absence_days,
    list_working_calendar,
    log_sms_reportable_change,
    record_sponsored_absence_day,
    recruitment_reference_links,
    refresh_sms_change_alert_statuses,
    store_immutable_rtw_pdf,
    upsert_working_calendar,
)

router = APIRouter(prefix="/compliance/sponsor-licence", tags=["Sponsor Licence Compliance"])
settings = load_settings()


class SmsChangeRequest(BaseModel):
    employee_id: int
    field_name: str = Field(pattern="^(job_title|salary|work_location)$")
    old_value: str | None = None
    new_value: str | None = None


class AdvertLinkInput(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=8, max_length=2048)
    type: str = "listing"


class AdvertisementRecordRequest(BaseModel):
    job_title: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=120)
    advert_url: str = Field(min_length=8, max_length=2048)
    posted_date: date
    job_reference: str | None = Field(default=None, max_length=120)
    soc_code: str | None = Field(default=None, max_length=20)
    vacancy_id: int | None = None
    advert_reference: str | None = Field(default=None, max_length=120)
    closing_date: date | None = None
    is_sponsored_vacancy: bool = True
    rlmt_applicable: bool = True
    minimum_advertising_days: int = Field(default=28, ge=1, le=365)
    additional_links: list[AdvertLinkInput] = Field(default_factory=list)
    extra_links: list[AdvertLinkInput] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=4000)


class AdvertisementLinkRequest(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=8, max_length=2048)
    type: str = "listing"


def _db_conn() -> Any:
    import os

    import psycopg2

    url = os.getenv("DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
    return psycopg2.connect(url)


async def _read_validated_pdf(upload: UploadFile) -> bytes:
    if upload.content_type not in {None, "application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Only PDF uploads are allowed")
    pdf_bytes = await upload.read()
    if len(pdf_bytes) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="PDF exceeds maximum upload size")
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Invalid PDF file")
    return pdf_bytes


@router.get("/checklist")
def rtw_checklist_link() -> dict[str, str]:
    return {
        "title": "UK Government Right to Work Checklist",
        "url": UK_RTW_CHECKLIST_URL,
        "note": "Use this official checklist when completing RTW checks.",
    }


@router.post("/rtw-checks")
async def create_rtw_check(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    employee_id: int = Form(...),
    check_date: date = Form(...),
    check_method: str = Form(...),
    outcome: str = Form(...),
    checker_user_id: str = Form(...),
    expiry_date: date | None = Form(None),
    gov_checklist_version: str | None = Form(None),
    evidence_pdf: UploadFile = File(...),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    pdf_bytes = await _read_validated_pdf(evidence_pdf)
    conn = _db_conn()
    try:
        stored = store_immutable_rtw_pdf(
            tenant_id=tenant_id,
            employee_id=employee_id,
            pdf_bytes=pdf_bytes,
            check_date=check_date,
            check_method=check_method,
            outcome=outcome,
            checker_user_id=checker_user_id or current_user.username,
            expiry_date=expiry_date,
            gov_checklist_version=gov_checklist_version,
            conn=conn,
        )
    finally:
        conn.close()
    return {
        "check_id": stored.check_id,
        "employee_id": stored.employee_id,
        "check_date": stored.check_date.isoformat(),
        "content_sha256": stored.content_sha256,
        "immutable_locked": stored.immutable_locked,
        "gov_checklist_url": stored.gov_checklist_url,
        "storage_path": stored.storage_path,
    }


@router.post("/absence-alerts/run")
def run_absence_alerts(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    as_of: date | None = None,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        alerts = evaluate_day9_absence_alerts(
            tenant_id=tenant_id,
            as_of=as_of or date.today(),
            conn=conn,
        )
    finally:
        conn.close()
    return {"generated": len(alerts), "alerts": alerts}


@router.post("/sms-changes")
def record_sms_change(
    payload: SmsChangeRequest,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    changed_by: str = Header(default="system", alias="X-User-Id"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        entry = log_sms_reportable_change(
            tenant_id=tenant_id,
            employee_id=payload.employee_id,
            field_name=payload.field_name,
            old_value=payload.old_value,
            new_value=payload.new_value,
            changed_by=changed_by or current_user.username,
            conn=conn,
        )
    finally:
        conn.close()
    if not entry:
        raise HTTPException(status_code=400, detail="No reportable SMS change detected")
    return entry


@router.post("/sms-changes/refresh-statuses")
def refresh_sms_statuses(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    as_of: date | None = None,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        updated = refresh_sms_change_alert_statuses(
            tenant_id=tenant_id,
            as_of=as_of or date.today(),
            conn=conn,
        )
    finally:
        conn.close()
    return {"updated": updated}


@router.get("/dashboard")
def sponsor_dashboard(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        data = compliance_dashboard(tenant_id=tenant_id, conn=conn)
    finally:
        conn.close()
    return data


@router.get("/recruitment-links")
def recruitment_links() -> dict[str, Any]:
    return {"links": recruitment_reference_links()}


@router.get("/advertisement-records")
def list_adverts(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    status: str | None = None,
    limit: int = 50,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        items = list_advertisement_records(tenant_id=tenant_id, conn=conn, status=status, limit=limit)
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.post("/advertisement-records")
def create_advert(
    payload: AdvertisementRecordRequest,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_user_id: str | None = Header(default="system", alias="X-User-Id"),
) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        record = create_advertisement_record(
            tenant_id=tenant_id,
            job_title=payload.job_title,
            platform=payload.platform,
            advert_url=payload.advert_url,
            posted_date=payload.posted_date,
            job_reference=payload.job_reference,
            soc_code=payload.soc_code,
            vacancy_id=payload.vacancy_id,
            advert_reference=payload.advert_reference,
            closing_date=payload.closing_date,
            is_sponsored_vacancy=payload.is_sponsored_vacancy,
            rlmt_applicable=payload.rlmt_applicable,
            minimum_advertising_days=payload.minimum_advertising_days,
            additional_links=[link.model_dump() for link in payload.additional_links],
            extra_links=[link.model_dump() for link in payload.extra_links],
            notes=payload.notes,
            created_by=x_user_id or current_user.username,
            conn=conn,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()
    return record


@router.get("/advertisement-records/{record_id}")
def get_advert(
    record_id: int,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        return get_advertisement_record(tenant_id=tenant_id, record_id=record_id, conn=conn)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@router.post("/advertisement-records/{record_id}/links")
def add_advert_link(
    record_id: int,
    payload: AdvertisementLinkRequest,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, Any]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        link = add_advertisement_link(
            tenant_id=tenant_id,
            record_id=record_id,
            link_label=payload.label,
            link_url=payload.url,
            link_type=payload.type,
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()
    return link


class AbsenceDayRequest(BaseModel):
    employee_id: int
    absence_date: date
    excuse_type: str = Field(default="unauthorized")
    is_excused: bool | None = None
    source: str = "admin"


class WorkingCalendarEntry(BaseModel):
    calendar_date: date
    is_working_day: bool = True


class WorkingCalendarBulkRequest(BaseModel):
    entries: list[WorkingCalendarEntry] = Field(min_length=1)


class ReportTriggerUpdate(BaseModel):
    status: str = Field(pattern="^(acknowledged|reported|dismissed)$")
    report_reference: str | None = None


@router.get("/absence-types")
def list_absence_types() -> dict[str, object]:
    return {"items": absence_type_catalog()}


@router.get("/absence-days")
def get_absence_days(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    employee_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 100,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        items = list_sponsored_absence_days(
            tenant_id=tenant_id,
            conn=conn,
            employee_id=employee_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.post("/absence-days")
def record_absence_day(
    payload: AbsenceDayRequest,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        result = record_sponsored_absence_day(
            tenant_id=tenant_id,
            employee_id=payload.employee_id,
            absence_date=payload.absence_date,
            excuse_type=payload.excuse_type,
            is_excused=payload.is_excused,
            source=payload.source,
            conn=conn,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()
    return result


@router.delete("/absence-days/{employee_id}/{absence_date}")
def remove_absence_day(
    employee_id: int,
    absence_date: date,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, str]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        deleted = delete_sponsored_absence_day(
            tenant_id=tenant_id,
            employee_id=employee_id,
            absence_date=absence_date,
            conn=conn,
        )
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Absence day not found")
    return {"status": "deleted"}


@router.get("/absence-streaks")
def absence_streaks(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    as_of: date | None = None,
    lookback_days: int = 30,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        items = get_absence_streak_summaries(
            tenant_id=tenant_id,
            as_of=as_of or date.today(),
            conn=conn,
            lookback_days=lookback_days,
        )
    finally:
        conn.close()
    return {"items": items, "count": len(items), "as_of": (as_of or date.today()).isoformat()}


@router.get("/working-calendar")
def get_working_calendar(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    from_date: date | None = None,
    to_date: date | None = None,
    non_working_only: bool = False,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        items = list_working_calendar(
            tenant_id=tenant_id,
            conn=conn,
            from_date=from_date,
            to_date=to_date,
            non_working_only=non_working_only,
        )
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.put("/working-calendar")
def update_working_calendar(
    payload: WorkingCalendarBulkRequest,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, int]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        result = upsert_working_calendar(
            tenant_id=tenant_id,
            entries=[entry.model_dump() for entry in payload.entries],
            conn=conn,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()
    return result


@router.get("/audit-export")
def audit_export(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    employee_id: int | None = None,
    format: str = "json",
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    from fastapi.responses import Response

    from modules.compliance.audit_export import build_audit_export
    from modules.compliance.audit_pdf import audit_export_pdf_bytes

    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        from admin_service import get_tenant_profile
        from plan_features import assert_plan_feature

        profile = get_tenant_profile(tenant_id=tenant_id, conn=conn)
        assert_plan_feature(
            profile["subscription_plan"],
            "audit_export",
            payroll_enabled=bool(profile["payroll_enabled"]),
        )
        if format.lower() == "pdf":
            pdf_bytes = audit_export_pdf_bytes(
                tenant_id=tenant_id, employee_id=employee_id, conn=conn
            )
            filename = f"audit-pack-tenant-{tenant_id}"
            if employee_id:
                filename += f"-employee-{employee_id}"
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
            )
        return build_audit_export(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    finally:
        conn.close()


class ShareCodeVerifyRequest(BaseModel):
    employee_id: int
    share_code: str = Field(min_length=6, max_length=32)
    date_of_birth: date


@router.post("/rtw-verify-share-code")
def verify_rtw_share_code(
    payload: ShareCodeVerifyRequest,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    from modules.compliance.idsp_rtw import IdspError, idsp_configured, persist_verification, verify_share_code

    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    try:
        verification = verify_share_code(
            share_code=payload.share_code,
            date_of_birth=payload.date_of_birth,
            employee_id=payload.employee_id,
            tenant_id=tenant_id,
        )
    except IdspError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    conn = _db_conn()
    try:
        result = persist_verification(
            conn=conn,
            tenant_id=tenant_id,
            employee_id=payload.employee_id,
            share_code=payload.share_code.strip().upper(),
            verification=verification,
            verified_by=current_user.username,
        )
    finally:
        conn.close()
    result["idsp_configured"] = idsp_configured()
    return result


@router.get("/reporting-triggers")
def list_reporting_triggers(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    status: str | None = "open",
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT id, employee_id, trigger_type, source_module, description,
                       deadline_date, status, created_at
                FROM sponsor_reporting_triggers WHERE tenant_id = %s
            """
            params: list[Any] = [tenant_id]
            if status:
                query += " AND status = %s"
                params.append(status)
            query += " ORDER BY deadline_date ASC LIMIT 200"
            cur.execute(query, params)
            items = [
                {
                    "id": r[0],
                    "employee_id": r[1],
                    "trigger_type": r[2],
                    "source_module": r[3],
                    "description": r[4],
                    "deadline_date": r[5].isoformat() if r[5] else None,
                    "status": r[6],
                    "created_at": r[7].isoformat() if r[7] else None,
                }
                for r in cur.fetchall()
            ]
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.patch("/reporting-triggers/{trigger_id}")
def update_reporting_trigger(
    trigger_id: int,
    payload: ReportTriggerUpdate,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, str]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = _db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sponsor_reporting_triggers
                SET status = %s,
                    reported_by = CASE WHEN %s = 'reported' THEN %s ELSE reported_by END,
                    reported_at = CASE WHEN %s = 'reported' THEN NOW() ELSE reported_at END,
                    report_reference = COALESCE(%s, report_reference)
                WHERE tenant_id = %s AND id = %s
                """,
                (
                    payload.status,
                    payload.status,
                    current_user.username,
                    payload.status,
                    payload.report_reference,
                    tenant_id,
                    trigger_id,
                ),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Trigger not found")
        conn.commit()
    finally:
        conn.close()
    return {"status": payload.status}
