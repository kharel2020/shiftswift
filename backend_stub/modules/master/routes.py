"""Platform master admin API — tenant register and overview metrics."""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth_service import AuthUser
from config import load_settings
from deps import client_ip, get_master_user
from modules.master.audit import write_master_audit
from modules.master.service import FilterStatus, get_tenant_detail, list_tenants, overview_stats

router = APIRouter(prefix="/master", tags=["Platform Master"])
settings = load_settings()


def _db_conn() -> Any:
    import psycopg2

    url = os.getenv("DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
    return psycopg2.connect(url)


@router.get("/overview")
def master_overview(
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_master_user)],
) -> dict[str, object]:
    conn = _db_conn()
    try:
        stats = overview_stats(conn=conn, master_tenant_id=int(settings.master_customer_id))
        write_master_audit(
            settings,
            master_username=current_user.username,
            action="VIEW_OVERVIEW",
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
        conn.commit()
        return {
            "provider_name": os.getenv("PROVIDER_LEGAL_NAME", "Datasoftware Analytics Ltd"),
            "stats": stats,
        }
    finally:
        conn.close()


@router.get("/tenants")
def master_tenant_list(
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_master_user)],
    status: FilterStatus = Query(default="all"),
    q: str | None = Query(default=None, max_length=120),
) -> dict[str, object]:
    conn = _db_conn()
    try:
        tenants = list_tenants(
            conn=conn,
            master_tenant_id=int(settings.master_customer_id),
            status_filter=status,
            search=q,
        )
        stats = overview_stats(conn=conn, master_tenant_id=int(settings.master_customer_id))
        write_master_audit(
            settings,
            master_username=current_user.username,
            action="LIST_TENANTS",
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            detail={"status": status, "q": q, "count": len(tenants)},
            conn=conn,
        )
        conn.commit()
        return {"tenants": tenants, "stats": stats["counts"], "overview": stats}
    finally:
        conn.close()


@router.get("/tenants/{tenant_id}")
def master_tenant_detail(
    tenant_id: int,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_master_user)],
) -> dict[str, object]:
    if tenant_id == int(settings.master_customer_id):
        raise HTTPException(status_code=404, detail="Tenant not found")

    conn = _db_conn()
    try:
        detail = get_tenant_detail(
            conn=conn,
            master_tenant_id=int(settings.master_customer_id),
            tenant_id=tenant_id,
        )
        if not detail:
            raise HTTPException(status_code=404, detail="Tenant not found")

        write_master_audit(
            settings,
            master_username=current_user.username,
            action="VIEW_TENANT",
            target_tenant_id=tenant_id,
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
        conn.commit()
        return {"tenant": detail}
    finally:
        conn.close()


@router.post("/tenants/{tenant_id}/impersonate")
def master_impersonate_tenant(
    tenant_id: int,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_master_user)],
) -> dict[str, object]:
    master_tid = int(settings.master_customer_id)
    if tenant_id == master_tid:
        raise HTTPException(status_code=400, detail="Cannot impersonate the platform master tenant")

    conn = _db_conn()
    try:
        from modules.master.impersonation import start_impersonation

        try:
            payload = start_impersonation(
                settings=settings,
                conn=conn,
                master_username=current_user.username,
                tenant_id=tenant_id,
                master_tenant_id=master_tid,
                ip_address=client_ip(request),
                user_agent=request.headers.get("User-Agent"),
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Tenant not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        conn.commit()
        return payload
    finally:
        conn.close()
