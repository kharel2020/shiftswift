"""Employee portal GDPR consent — employer is data controller."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from auth_service import fetch_user_from_db
from config import Settings

EMPLOYEE_GDPR_CONSENT_VERSION = "2026-06-10"


def tenant_display_name(*, tenant_id: int, conn: Any) -> str:
    from admin_service import get_tenant_profile

    profile = get_tenant_profile(tenant_id=tenant_id, conn=conn)
    return str(profile.get("trading_name") or profile.get("name") or "Your employer")


def has_employee_gdpr_consent(*, tenant_id: int, username: str, conn: Any) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM employee_portal_gdpr_consents
            WHERE tenant_id = %s AND lower(username) = lower(%s)
            LIMIT 1
            """,
            (tenant_id, username),
        )
        return cur.fetchone() is not None


def record_employee_gdpr_consent(
    *,
    tenant_id: int,
    username: str,
    employer_name: str,
    ip_address: str | None,
    user_agent: str | None,
    conn: Any,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO employee_portal_gdpr_consents (
              tenant_id, username, consent_version, employer_name, ip_address, user_agent
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, username) DO NOTHING
            """,
            (
                tenant_id,
                username.strip(),
                EMPLOYEE_GDPR_CONSENT_VERSION,
                employer_name,
                ip_address,
                user_agent,
            ),
        )


def validate_employee_gdpr_acceptance(*, accept_employee_gdpr: bool) -> None:
    if not accept_employee_gdpr:
        raise ValueError(
            "Please confirm you understand your employer manages your personal data "
            "and agree to the privacy notice before continuing."
        )


def get_password_reset_context(
    *,
    settings: Settings,
    conn: Any,
    raw_token: str,
) -> dict[str, object]:
    from auth_password_reset import _hash_token

    token_hash = _hash_token(raw_token.strip())
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT username
            FROM password_reset_tokens
            WHERE token_hash = %s
              AND used_at IS NULL
              AND expires_at > %s
            LIMIT 1
            """,
            (token_hash, now),
        )
        row = cur.fetchone()
        if not row:
            raise LookupError("This reset link is invalid or has expired. Request a new one.")
        username = row[0]

    user = fetch_user_from_db(settings, username)
    if not user or not user.get("is_active"):
        raise LookupError("This reset link is invalid or has expired. Request a new one.")

    tenant_id = int(user["tenant_id"])
    role = str(user.get("role") or "")
    requires_gdpr_consent = False
    employer_name = ""
    if role == "employee":
        employer_name = tenant_display_name(tenant_id=tenant_id, conn=conn)
        requires_gdpr_consent = not has_employee_gdpr_consent(
            tenant_id=tenant_id,
            username=username,
            conn=conn,
        )

    return {
        "role": role,
        "employer_name": employer_name,
        "requires_gdpr_consent": requires_gdpr_consent,
        "privacy_policy_url": "/privacy-policy.html",
    }
