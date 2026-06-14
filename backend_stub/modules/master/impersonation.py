"""Start a short-lived impersonation session for platform master admins."""

from __future__ import annotations

from typing import Any

from auth_service import create_impersonation_access_token, log_security_event
from config import Settings
from modules.master.audit import write_master_audit


def start_impersonation(
    *,
    settings: Settings,
    conn: Any,
    master_username: str,
    tenant_id: int,
    master_tenant_id: int,
    ip_address: str | None,
    user_agent: str | None,
) -> dict[str, object]:
    if tenant_id == master_tenant_id:
        raise ValueError("Cannot impersonate the platform master tenant")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, platform_status, deleted_at FROM tenants WHERE id = %s",
            (tenant_id,),
        )
        row = cur.fetchone()
    if not row:
        raise LookupError("tenant not found")
    if row[3] is not None:
        raise ValueError("Cannot impersonate a deleted tenant")
    if (row[2] or "active").strip().lower() == "suspended":
        raise ValueError("Cannot impersonate a suspended tenant — re-enable the account first")

    _tenant_id, tenant_name = row[0], row[1]
    access_token, expires_in = create_impersonation_access_token(
        settings,
        master_username=master_username,
        tenant_id=tenant_id,
    )

    write_master_audit(
        settings,
        master_username=master_username,
        action="IMPERSONATE",
        target_tenant_id=tenant_id,
        ip_address=ip_address,
        user_agent=user_agent,
        detail={"tenant_name": tenant_name, "expires_in": expires_in},
        conn=conn,
    )
    log_security_event(
        settings,
        event_type="master_impersonation_started",
        username=master_username,
        tenant_id=str(tenant_id),
        ip_address=ip_address,
        user_agent=user_agent,
        success=True,
        detail=f"impersonated_by={master_username}",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": "hr",
        "tenant_id": str(tenant_id),
        "tenant_name": tenant_name,
        "expires_in": expires_in,
        "impersonated_by": master_username,
        "redirect_url": "./admin.html",
    }
