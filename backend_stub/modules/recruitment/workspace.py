"""Recruitment vacancy workspace — 10-step pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from admin_service import create_employee
from modules.documents.service import validate_email
from modules.recruitment.constants import (
    LINK_ONLY_SECTIONS,
    SECTION_BRANCHES,
    SECTION_DESCRIPTIONS,
    SECTION_KINDS,
    SECTION_LABELS,
    SECTION_ORDER,
    SECTION_STEPS,
)
from modules.recruitment.repository import (
    clear_primary_applications,
    create_application,
    fetch_vacancy,
    list_applications,
    list_vacancy_adverts,
    section_field_names,
    sync_primary_candidate_to_vacancy,
    update_application,
    update_vacancy_fields,
)


def _compute_match_score(vacancy: dict[str, Any], application: dict[str, Any]) -> int | None:
    keywords = str(vacancy.get("screening_keywords") or "").strip()
    if not keywords:
        return None
    haystack = " ".join(
        filter(
            None,
            [
                application.get("candidate_name"),
                application.get("application_source"),
                application.get("screening_notes"),
            ],
        )
    ).lower()
    tokens = [token.strip().lower() for token in keywords.replace("\n", ",").split(",") if token.strip()]
    if not tokens:
        return None
    hits = sum(1 for token in tokens if token in haystack)
    return min(100, int(round((hits / len(tokens)) * 100)))


def _application_counts(applications: list[dict[str, Any]], vacancy: dict[str, Any]) -> tuple[int, int]:
    if applications:
        return len(applications), sum(1 for app in applications if app.get("screening_status") == "shortlisted")
    candidate_count = 1 if _is_filled(vacancy.get("candidate_name")) else 0
    shortlisted_count = 1 if vacancy.get("candidate_rating") is not None else 0
    return candidate_count, shortlisted_count


def _enrich_applications(vacancy: dict[str, Any], applications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for app in applications:
        score = app.get("match_score")
        if score is None:
            score = _compute_match_score(vacancy, app)
        enriched.append({**app, "match_score": score})
    return enriched


def _is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _section_data(section: str, vacancy: dict[str, Any]) -> dict[str, Any]:
    if section == "multi_channel_posting":
        return {"advert_count": vacancy.get("_advert_count", 0)}
    if section == "offer_accepted":
        return {
            "offer_status": vacancy.get("offer_status"),
            "employee_id": vacancy.get("employee_id"),
            "status": vacancy.get("status"),
        }
    return {field: vacancy.get(field) for field in section_field_names(section)}


def _section_complete(section: str, vacancy: dict[str, Any]) -> bool:
    if section in LINK_ONLY_SECTIONS:
        return vacancy.get("_advert_count", 0) > 0
    if section == "vacancy_identified":
        return _is_filled(vacancy.get("job_title"))
    if section == "job_description":
        return _is_filled(vacancy.get("job_description")) and (
            vacancy.get("salary_range_min") is not None or vacancy.get("salary_range_max") is not None
        )
    if section == "application_intake":
        apps = vacancy.get("_applications") or []
        if apps:
            return len(apps) > 0
        return _is_filled(vacancy.get("candidate_name")) and _is_filled(vacancy.get("candidate_email"))
    if section == "automated_screening":
        apps = vacancy.get("_applications") or []
        rules_saved = _is_filled(vacancy.get("screening_keywords")) or _is_filled(vacancy.get("knockout_questions"))
        if apps:
            pending = sum(1 for app in apps if app.get("screening_status") == "pending")
            shortlisted = sum(1 for app in apps if app.get("screening_status") == "shortlisted")
            return rules_saved and pending == 0 and shortlisted > 0
        return rules_saved
    if section == "candidate_pipeline":
        return vacancy.get("candidate_rating") is not None or _is_filled(vacancy.get("pipeline_notes"))
    if section == "interview_scheduling":
        return _is_filled(vacancy.get("interview_at"))
    if section == "hiring_decision":
        return vacancy.get("hiring_decision") in ("hire", "reject")
    if section == "offer_management":
        if vacancy.get("hiring_decision") == "reject":
            return True
        return vacancy.get("offer_status") in ("sent", "accepted", "rejected") and _is_filled(
            vacancy.get("offer_salary")
        )
    if section == "offer_accepted":
        return vacancy.get("status") in ("offer_accepted", "onboarding_started", "closed") or bool(
            vacancy.get("employee_id")
        )
    return False


def _section_applicable(section: str, vacancy: dict[str, Any]) -> bool:
    if vacancy.get("hiring_decision") == "reject" and section in (
        "offer_management",
        "offer_accepted",
    ):
        return False
    if vacancy.get("status") == "rejected" and section in ("offer_management", "offer_accepted"):
        return False
    return True


def _build_sections(*, vacancy: dict[str, Any]) -> list[dict[str, Any]]:
    sections = []
    for key in SECTION_ORDER:
        if not _section_applicable(key, vacancy):
            continue
        sections.append(
            {
                "key": key,
                "step": SECTION_STEPS[key],
                "label": SECTION_LABELS[key],
                "description": SECTION_DESCRIPTIONS[key],
                "branch": SECTION_BRANCHES.get(key),
                "kind": SECTION_KINDS[key],
                "complete": _section_complete(key, vacancy),
                "data": _section_data(key, vacancy),
            }
        )
    return sections


def list_vacancy_completion_summary(
    vacancy: dict[str, Any],
    *,
    advert_count: int = 0,
    applications: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    enriched = {**vacancy, "_advert_count": advert_count, "_applications": applications or []}
    sections = _build_sections(vacancy=enriched)
    editable = [s for s in sections if s["kind"] in ("form", "action", "link")]
    completed = sum(1 for s in editable if s["complete"])
    completion_pct = int(round((completed / len(editable)) * 100)) if editable else 0
    next_section = next(
        (s["key"] for s in sections if not s["complete"] and s["kind"] in ("form", "action", "link")),
        None,
    )
    current_step = SECTION_STEPS.get(next_section) if next_section else len(SECTION_ORDER)
    current_step_label = SECTION_LABELS.get(next_section, "Complete") if next_section else "Complete"
    candidate_count, shortlisted_count = _application_counts(applications or [], vacancy)
    return {
        "completion_pct": completion_pct,
        "next_section": next_section,
        "current_step": current_step,
        "current_step_label": current_step_label,
        "completed_steps": completed,
        "total_steps": len(editable),
        "candidate_count": candidate_count,
        "shortlisted_count": shortlisted_count,
    }


def fetch_advert_counts_by_vacancy(*, tenant_id: int, conn: Any) -> dict[int, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT vacancy_id, COUNT(*)
            FROM recruitment_advertisement_records
            WHERE tenant_id = %s AND vacancy_id IS NOT NULL
            GROUP BY vacancy_id
            """,
            (tenant_id,),
        )
        return {int(vacancy_id): int(count) for vacancy_id, count in cur.fetchall()}


def build_workspace(*, tenant_id: int, vacancy_id: int, conn: Any) -> dict[str, Any]:
    vacancy = fetch_vacancy(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)
    if not vacancy:
        raise LookupError("vacancy not found")

    adverts = list_vacancy_adverts(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)
    applications = _enrich_applications(vacancy, list_applications(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn))
    vacancy["_advert_count"] = len(adverts)
    vacancy["_applications"] = applications

    sections = _build_sections(vacancy=vacancy)
    summary = list_vacancy_completion_summary(vacancy, advert_count=len(adverts), applications=applications)

    return {
        "vacancy": vacancy,
        "adverts": adverts,
        "applications": applications,
        "sections": sections,
        "completion_pct": summary["completion_pct"],
        "next_section": summary["next_section"],
        "current_step": summary["current_step"],
        "current_step_label": summary["current_step_label"],
        "candidate_count": summary["candidate_count"],
        "shortlisted_count": summary["shortlisted_count"],
        "completed_steps": summary["completed_steps"],
        "total_steps": summary["total_steps"],
        "onboarding_ready": bool(vacancy.get("employee_id")),
    }


def patch_section(
    *,
    tenant_id: int,
    vacancy_id: int,
    section: str,
    updates: dict[str, Any],
    actor_username: str,
    actor_role: str,
    conn: Any,
) -> dict[str, Any]:
    if section not in SECTION_ORDER or section in LINK_ONLY_SECTIONS or section == "offer_accepted":
        raise ValueError("invalid section")

    vacancy = fetch_vacancy(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)
    if not vacancy:
        raise LookupError("vacancy not found")

    allowed = section_field_names(section)
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if section == "hiring_decision" and filtered.get("hiring_decision") == "reject":
        filtered["status"] = "rejected"
        filtered["offer_status"] = "rejected"
    if not filtered:
        raise ValueError("no fields to update")

    if section == "application_intake" and "candidate_email" in filtered:
        validate_email(filtered.get("candidate_email"), field_label="Candidate email")

    if section == "offer_management":
        if filtered.get("offer_status") == "sent" and not vacancy.get("offer_sent_at"):
            filtered["offer_sent_at"] = datetime.utcnow()
        if filtered.get("offer_status") == "draft":
            filtered["offer_sent_at"] = None

    filtered["current_stage"] = section
    update_vacancy_fields(tenant_id=tenant_id, vacancy_id=vacancy_id, updates=filtered, conn=conn)
    return build_workspace(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)


def fetch_application_counts_by_vacancy(*, tenant_id: int, conn: Any) -> dict[int, list[dict[str, Any]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT vacancy_id, screening_status, COUNT(*)
            FROM recruitment_applications
            WHERE tenant_id = %s
            GROUP BY vacancy_id, screening_status
            """,
            (tenant_id,),
        )
        grouped: dict[int, list[tuple[str, int]]] = {}
        for vacancy_id, status, count in cur.fetchall():
            grouped.setdefault(int(vacancy_id), []).append((status, int(count)))
    return grouped


def add_vacancy_application(
    *,
    tenant_id: int,
    vacancy_id: int,
    data: dict[str, Any],
    conn: Any,
) -> dict[str, Any]:
    vacancy = fetch_vacancy(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)
    if not vacancy:
        raise LookupError("vacancy not found")
    if not _is_filled(data.get("candidate_name")):
        raise ValueError("candidate name required")
    if data.get("candidate_email"):
        validate_email(data.get("candidate_email"), field_label="Candidate email")

    application = create_application(tenant_id=tenant_id, vacancy_id=vacancy_id, data=data, conn=conn)
    if not _is_filled(vacancy.get("candidate_name")):
        sync_primary_candidate_to_vacancy(
            tenant_id=tenant_id,
            vacancy_id=vacancy_id,
            application=application,
            conn=conn,
        )
    return build_workspace(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)


def patch_vacancy_application(
    *,
    tenant_id: int,
    vacancy_id: int,
    application_id: int,
    updates: dict[str, Any],
    conn: Any,
) -> dict[str, Any]:
    vacancy = fetch_vacancy(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)
    if not vacancy:
        raise LookupError("vacancy not found")

    allowed = {"screening_status", "screening_notes", "is_primary"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        raise ValueError("no fields to update")

    if filtered.get("screening_status") == "shortlisted":
        clear_primary_applications(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)
        filtered["is_primary"] = True

    application = update_application(
        tenant_id=tenant_id,
        vacancy_id=vacancy_id,
        application_id=application_id,
        updates=filtered,
        conn=conn,
    )

    if application.get("is_primary") or filtered.get("screening_status") == "shortlisted":
        sync_primary_candidate_to_vacancy(
            tenant_id=tenant_id,
            vacancy_id=vacancy_id,
            application=application,
            conn=conn,
        )

    return build_workspace(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)


def accept_offer_and_start_onboarding(
    *,
    tenant_id: int,
    vacancy_id: int,
    actor_username: str,
    actor_role: str,
    conn: Any,
) -> dict[str, Any]:
    vacancy = fetch_vacancy(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)
    if not vacancy:
        raise LookupError("vacancy not found")
    if vacancy.get("hiring_decision") != "hire":
        raise ValueError("hiring decision must be hire before accepting offer")
    if not _is_filled(vacancy.get("candidate_name")):
        raise ValueError("candidate name required")
    if vacancy.get("employee_id"):
        return build_workspace(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)

    name_parts = str(vacancy["candidate_name"]).strip().split(None, 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else "—"
    salary = vacancy.get("offer_salary") or vacancy.get("salary_range_min") or vacancy.get("salary_range_max")

    employee = create_employee(
        tenant_id=tenant_id,
        data={
            "first_name": first_name,
            "last_name": last_name,
            "email": vacancy.get("candidate_email"),
            "job_title": vacancy.get("job_title"),
            "department": vacancy.get("department"),
            "work_location": vacancy.get("location"),
            "salary": salary,
            "status": "onboarding",
            "is_sponsored": vacancy.get("worker_type") == "sponsored",
            "phone": vacancy.get("candidate_phone"),
        },
        actor_username=actor_username,
        actor_role=actor_role,
        ip_address=None,
        user_agent=None,
        conn=conn,
    )

    update_vacancy_fields(
        tenant_id=tenant_id,
        vacancy_id=vacancy_id,
        updates={
            "offer_status": "accepted",
            "status": "onboarding_started",
            "current_stage": "offer_accepted",
            "employee_id": employee["id"],
        },
        conn=conn,
    )

    workspace = build_workspace(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)
    workspace["employee"] = employee
    workspace["onboarding_url"] = f"employees/{employee['id']}/onboarding"
    return workspace
