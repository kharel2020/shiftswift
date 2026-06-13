"""Provision employee portal logins and send setup emails."""

from __future__ import annotations

import re
import secrets
from typing import Any

from auth_password_reset import RESET_HOURS, send_account_setup_email
from auth_service import fetch_user_from_db, hash_password
from config import Settings
from employee_audit import log_employee_data_event
from modules.employees.repository import fetch_employee

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INVITE_EMPLOYEE_STATUSES = frozenset({"active", "onboarding"})


def _normalize_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def _looks_like_email(value: str | None) -> bool:
    return bool(value and EMAIL_RE.match(value))


def fetch_portal_account_by_email(*, conn: Any, email: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT username, role, tenant_id::text AS tenant_id, is_active, login_portal
            FROM app_users
            WHERE lower(username) = lower(%s)
            LIMIT 1
            """,
            (email,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "username": row[0],
        "role": row[1],
        "tenant_id": row[2],
        "is_active": bool(row[3]),
        "login_portal": row[4],
    }


def enrich_employees_portal_status(
    *,
    tenant_id: int,
    employees: list[dict[str, Any]],
    conn: Any,
) -> list[dict[str, Any]]:
    emails = [_normalize_email(item.get("email")) for item in employees if _looks_like_email(item.get("email"))]
    portal_by_email: dict[str, dict[str, Any]] = {}
    if emails:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT lower(username), role, tenant_id::text, is_active
                FROM app_users
                WHERE lower(username) = ANY(%s)
                """,
                (emails,),
            )
            for username, role, account_tenant_id, is_active in cur.fetchall():
                portal_by_email[username] = {
                    "role": role,
                    "tenant_id": account_tenant_id,
                    "is_active": bool(is_active),
                }

    enriched: list[dict[str, Any]] = []
    for item in employees:
        email = _normalize_email(item.get("email"))
        account = portal_by_email.get(email) if email else None
        has_portal = bool(
            account
            and account["role"] == "employee"
            and str(account["tenant_id"]) == str(tenant_id)
            and account["is_active"]
        )
        eligible = (
            _looks_like_email(email)
            and item.get("status") in INVITE_EMPLOYEE_STATUSES
            and not has_portal
        )
        enriched.append(
            {
                **item,
                "portal_has_account": has_portal,
                "portal_invite_eligible": eligible,
            }
        )
    return enriched


def _ensure_employee_app_user(
    *,
    tenant_id: int,
    email: str,
    conn: Any,
    settings: Settings,
) -> tuple[dict[str, Any], bool]:
    existing = fetch_portal_account_by_email(conn=conn, email=email)
    if existing:
        if existing["role"] == "hr":
            raise ValueError("This email is already used for HR admin login — use a different work email")
        if existing["role"] == "admin" or existing.get("login_portal") not in {None, "business"}:
            raise ValueError("This email cannot be used for an employee portal account")
        if str(existing["tenant_id"]) != str(tenant_id):
            raise ValueError("This email is already registered on another ShiftSwift HR account")
        if not existing["is_active"]:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE app_users
                    SET is_active = TRUE, updated_at = NOW()
                    WHERE lower(username) = lower(%s)
                    """,
                    (email,),
                )
            existing["is_active"] = True
        user = fetch_user_from_db(settings, email)
        if not user:
            raise ValueError("Could not load employee login account")
        return user, False

    password_hash = hash_password(secrets.token_urlsafe(32))
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_users (username, password_hash, role, tenant_id, login_portal)
            VALUES (%s, %s, 'employee', %s, 'business')
            """,
            (email, password_hash, tenant_id),
        )
    user = fetch_user_from_db(settings, email)
    if not user:
        raise ValueError("Could not create employee login account")
    return user, True


def invite_employee_to_portal(
    *,
    tenant_id: int,
    employee_id: int,
    conn: Any,
    settings: Settings,
    actor_username: str,
    actor_role: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    resend_if_exists: bool = True,
) -> dict[str, Any]:
    employee = fetch_employee(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    if not employee:
        raise LookupError("employee not found")

    email = _normalize_email(employee.get("email"))
    if not _looks_like_email(email):
        raise ValueError("Add a work email on the employee profile before sending a portal invite")
    if employee.get("status") not in INVITE_EMPLOYEE_STATUSES:
        raise ValueError("Portal invites are only available for active or onboarding employees")

    existing = fetch_portal_account_by_email(conn=conn, email=email)
    has_portal = bool(
        existing
        and existing["role"] == "employee"
        and str(existing["tenant_id"]) == str(tenant_id)
        and existing["is_active"]
    )
    if has_portal and not resend_if_exists:
        raise ValueError("This employee already has a portal account")

    user, created = _ensure_employee_app_user(
        tenant_id=tenant_id,
        email=email,
        conn=conn,
        settings=settings,
    )

    from admin_service import get_tenant_profile
    from core.email_templates import employee_portal_invite_email

    profile = get_tenant_profile(tenant_id=tenant_id, conn=conn)
    tenant_name = profile.get("trading_name") or profile.get("name") or "Your employer"
    employee_name = f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip() or "there"

    import os

    app_url = os.getenv("APP_URL", "https://app.shiftswifthr.co.uk").rstrip("/")
    send_account_setup_email(
        settings=settings,
        conn=conn,
        user=user,
        content_factory=lambda reset_url: employee_portal_invite_email(
            employee_name=employee_name,
            tenant_name=tenant_name,
            setup_url=reset_url,
            login_url=f"{app_url}/business-login.html",
            reset_hours=RESET_HOURS,
        ),
        ip_address=ip_address,
        user_agent=user_agent,
        security_event_type="employee_portal_invite_sent",
        commit=False,
    )

    log_employee_data_event(
        tenant_id=tenant_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action="invite",
        entity_type="employee_portal",
        entity_id=employee_id,
        field_name=email,
        new_value="created" if created else "resent",
        ip_address=ip_address,
        user_agent=user_agent,
        conn=conn,
    )
    conn.commit()

    message = (
        f"Portal invite sent to {email}"
        if created
        else f"Portal setup link resent to {email}"
    )
    return {
        "employee_id": employee_id,
        "email": email,
        "created_account": created,
        "portal_has_account": True,
        "message": message,
    }


def invite_missing_portal_accounts(
    *,
    tenant_id: int,
    conn: Any,
    settings: Settings,
    actor_username: str,
    actor_role: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    resend_existing: bool = False,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, first_name, last_name, email, status
            FROM employees
            WHERE tenant_id = %s AND status = ANY(%s)
            ORDER BY last_name, first_name
            """,
            (tenant_id, list(INVITE_EMPLOYEE_STATUSES)),
        )
        rows = cur.fetchall()

    invited: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for employee_id, first_name, last_name, email, status in rows:
        label = f"{first_name} {last_name}".strip()
        if not _looks_like_email(email):
            skipped.append({"employee_id": employee_id, "name": label, "reason": "no work email"})
            continue

        existing = fetch_portal_account_by_email(conn=conn, email=_normalize_email(email))
        has_portal = bool(
            existing
            and existing["role"] == "employee"
            and str(existing["tenant_id"]) == str(tenant_id)
            and existing["is_active"]
        )
        if has_portal and not resend_existing:
            skipped.append({"employee_id": employee_id, "name": label, "reason": "already has portal account"})
            continue

        try:
            result = invite_employee_to_portal(
                tenant_id=tenant_id,
                employee_id=int(employee_id),
                conn=conn,
                settings=settings,
                actor_username=actor_username,
                actor_role=actor_role,
                ip_address=ip_address,
                user_agent=user_agent,
                resend_if_exists=resend_existing,
            )
            invited.append(
                {
                    "employee_id": result["employee_id"],
                    "name": label,
                    "email": result["email"],
                    "created_account": result["created_account"],
                }
            )
        except ValueError as exc:
            failed.append({"employee_id": employee_id, "name": label, "reason": str(exc)})

    created_count = sum(1 for item in invited if item.get("created_account"))
    resent_count = len(invited) - created_count
    parts = []
    if created_count:
        parts.append(f"{created_count} new account{'s' if created_count != 1 else ''}")
    if resent_count:
        parts.append(f"{resent_count} resent")
    summary = ", ".join(parts) if parts else "No invites sent"

    return {
        "invited_count": len(invited),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "invited": invited,
        "skipped": skipped,
        "failed": failed,
        "message": f"{summary}. {len(skipped)} skipped, {len(failed)} failed.",
    }
