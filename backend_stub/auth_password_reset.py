"""Password reset tokens and email delivery."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from auth_service import fetch_user_from_db, hash_password, log_security_event
from config import Settings
from core.notifications import send_email_content

PortalRole = Literal["hr", "employee", "any"]
RESET_HOURS = int(os.getenv("PASSWORD_RESET_HOURS", "2"))


def _app_url() -> str:
    return os.getenv("APP_URL", "https://app.shiftswifthr.co.uk").rstrip("/")


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _find_business_user(
    settings: Settings,
    *,
    email: str,
    role_hint: PortalRole,
) -> dict[str, Any] | None:
    row = fetch_user_from_db(settings, email.strip())
    if not row or not row.get("is_active"):
        return None
    if row.get("role") == "admin" or row.get("login_portal") != "business":
        return None
    if role_hint == "hr" and row.get("role") != "hr":
        return None
    if role_hint == "employee" and row.get("role") != "employee":
        return None
    return row


def request_password_reset(
    *,
    settings: Settings,
    conn: Any,
    email: str,
    role_hint: PortalRole = "any",
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str]:
    """Create reset token and queue email. Always returns the same public message."""
    user = _find_business_user(settings, email=email, role_hint=role_hint)
    if user:
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires = datetime.now(timezone.utc) + timedelta(hours=RESET_HOURS)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = NOW()
                WHERE username = %s AND used_at IS NULL
                """,
                (user["username"],),
            )
            cur.execute(
                """
                INSERT INTO password_reset_tokens
                  (username, token_hash, expires_at, ip_address, user_agent)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user["username"], token_hash, expires, ip_address, user_agent),
            )
        reset_url = f"{_app_url()}/reset-password.html?token={raw_token}"
        role_label = "employee" if user["role"] == "employee" else "HR admin"
        from core.email_templates import password_reset_email

        content = password_reset_email(
            role_label=role_label,
            reset_url=reset_url,
            reset_hours=RESET_HOURS,
        )
        audience = "employee" if user["role"] == "employee" else "hr"
        send_email_content(
            conn=conn,
            tenant_id=int(user["tenant_id"]),
            content=content,
            purpose="password_reset",
            to=user["username"],
            audience=audience,
            deliver_now=True,
            commit=False,
        )
        log_security_event(
            settings,
            event_type="password_reset_requested",
            username=user["username"],
            tenant_id=str(user["tenant_id"]),
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )
        conn.commit()
    return {
        "message": (
            "If an account exists for that email, we sent a password reset link. "
            "Check your inbox and spam folder."
        )
    }


def complete_password_reset(
    *,
    settings: Settings,
    conn: Any,
    raw_token: str,
    new_password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str]:
    if len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters")
    token_hash = _hash_token(raw_token.strip())
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, username
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
        token_id, username = row[0], row[1]
        user = fetch_user_from_db(settings, username)
        if not user or not user.get("is_active"):
            raise LookupError("This reset link is invalid or has expired. Request a new one.")
        cur.execute(
            """
            UPDATE app_users
            SET password_hash = %s, updated_at = NOW(), failed_login_attempts = 0, locked_until = NULL
            WHERE lower(username) = lower(%s)
            """,
            (hash_password(new_password), username),
        )
        cur.execute(
            "UPDATE password_reset_tokens SET used_at = NOW() WHERE id = %s",
            (token_id,),
        )
    conn.commit()
    log_security_event(
        settings,
        event_type="password_reset_completed",
        username=username,
        tenant_id=str(user["tenant_id"]),
        ip_address=ip_address,
        user_agent=user_agent,
        success=True,
    )
    return {"message": "Password updated. You can sign in with your new password."}
