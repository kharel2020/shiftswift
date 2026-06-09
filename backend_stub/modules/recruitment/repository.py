"""Recruitment vacancy data access."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from modules.recruitment.constants import SECTION_FIELDS

VACANCY_COLUMNS = (
    "id",
    "reference",
    "job_title",
    "department",
    "location",
    "job_description",
    "required_skills",
    "salary_range_min",
    "salary_range_max",
    "screening_keywords",
    "knockout_questions",
    "candidate_name",
    "candidate_email",
    "candidate_phone",
    "candidate_cv_url",
    "application_source",
    "pipeline_notes",
    "candidate_rating",
    "interview_at",
    "interview_video_link",
    "scorecard_notes",
    "hiring_decision",
    "rejection_reason",
    "offer_letter_url",
    "offer_status",
    "worker_type",
    "current_stage",
    "status",
    "employee_id",
    "created_at",
    "updated_at",
)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _row_to_vacancy(row: tuple[Any, ...]) -> dict[str, Any]:
    data = dict(zip(VACANCY_COLUMNS, row, strict=True))
    for key in ("salary_range_min", "salary_range_max"):
        if data[key] is not None:
            data[key] = float(data[key])
    data["interview_at"] = _iso(data.get("interview_at"))
    data["created_at"] = _iso(data.get("created_at"))
    data["updated_at"] = _iso(data.get("updated_at"))
    return data


def list_vacancies(*, tenant_id: int, conn: Any, limit: int = 100) -> list[dict[str, Any]]:
    cols = ", ".join(VACANCY_COLUMNS)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {cols}
            FROM recruitment_vacancies
            WHERE tenant_id = %s
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (tenant_id, limit),
        )
        return [_row_to_vacancy(row) for row in cur.fetchall()]


def fetch_vacancy(*, tenant_id: int, vacancy_id: int, conn: Any) -> dict[str, Any] | None:
    cols = ", ".join(VACANCY_COLUMNS)
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {cols} FROM recruitment_vacancies WHERE tenant_id = %s AND id = %s",
            (tenant_id, vacancy_id),
        )
        row = cur.fetchone()
    return _row_to_vacancy(row) if row else None


def create_vacancy(*, tenant_id: int, data: dict[str, Any], conn: Any) -> dict[str, Any]:
    cols = ", ".join(VACANCY_COLUMNS[1:-2])  # exclude id, created_at, updated_at from insert list
    # Simpler explicit insert
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO recruitment_vacancies (
              tenant_id, job_title, department, location, reference, worker_type
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING """
            + ", ".join(VACANCY_COLUMNS),
            (
                tenant_id,
                data["job_title"],
                data.get("department"),
                data.get("location"),
                data.get("reference"),
                data.get("worker_type", "standard"),
            ),
        )
        row = cur.fetchone()
        conn.commit()
    return _row_to_vacancy(row)


def update_vacancy_fields(
    *,
    tenant_id: int,
    vacancy_id: int,
    updates: dict[str, Any],
    conn: Any,
) -> dict[str, Any]:
    if not updates:
        vacancy = fetch_vacancy(tenant_id=tenant_id, vacancy_id=vacancy_id, conn=conn)
        if not vacancy:
            raise LookupError("vacancy not found")
        return vacancy

    updates = {**updates, "updated_at": datetime.utcnow()}
    sets = ", ".join(f"{key} = %s" for key in updates)
    values = list(updates.values()) + [tenant_id, vacancy_id]
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE recruitment_vacancies SET {sets}
            WHERE tenant_id = %s AND id = %s
            RETURNING {", ".join(VACANCY_COLUMNS)}
            """,
            values,
        )
        row = cur.fetchone()
        if not row:
            raise LookupError("vacancy not found")
        conn.commit()
    return _row_to_vacancy(row)


def list_vacancy_adverts(*, tenant_id: int, vacancy_id: int, conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, job_title, platform, advert_url, posted_date, record_status
            FROM recruitment_advertisement_records
            WHERE tenant_id = %s AND vacancy_id = %s
            ORDER BY posted_date DESC
            """,
            (tenant_id, vacancy_id),
        )
        rows = cur.fetchall()
    return [
        {
            "id": row[0],
            "job_title": row[1],
            "platform": row[2],
            "advert_url": row[3],
            "posted_date": _iso(row[4]),
            "record_status": row[5],
        }
        for row in rows
    ]


def section_field_names(section: str) -> tuple[str, ...]:
    return SECTION_FIELDS.get(section, ())
