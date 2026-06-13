"""Employee Web Push subscription routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from auth_service import AuthUser
from config import load_settings
from core.database import get_connection
from deps import client_ip, get_employee_user, resolve_tenant_id
from modules.push import service as push_service
from modules.time_punch.service import resolve_employee

settings = load_settings()

router = APIRouter(prefix="/employee/push", tags=["Push notifications"])


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=8)
    keys: PushKeys


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=8)


def _employee_for_user(*, tenant_id: int, user: AuthUser, conn: Any) -> dict[str, Any]:
    employee = resolve_employee(tenant_id=tenant_id, username=user.username, conn=conn)
    if not employee:
        raise HTTPException(
            status_code=404,
            detail="No employee record linked to this login.",
        )
    return employee


@router.get("/config")
def push_config(
    current_user: Annotated[AuthUser, Depends(get_employee_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    return push_service.push_config_payload()


@router.post("/subscribe")
def push_subscribe(
    payload: PushSubscribeRequest,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_employee_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    if not push_service.push_configured():
        raise HTTPException(
            status_code=503,
            detail="Push notifications are not configured on this server.",
        )
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        employee = _employee_for_user(tenant_id=tenant_id, user=current_user, conn=conn)
        row = push_service.upsert_subscription(
            tenant_id=tenant_id,
            employee_id=employee["id"],
            endpoint=payload.endpoint.strip(),
            p256dh=payload.keys.p256dh.strip(),
            auth=payload.keys.auth.strip(),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
    finally:
        conn.close()
    return {"ok": True, **row}


@router.post("/unsubscribe")
def push_unsubscribe(
    payload: PushUnsubscribeRequest,
    current_user: Annotated[AuthUser, Depends(get_employee_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        employee = _employee_for_user(tenant_id=tenant_id, user=current_user, conn=conn)
        removed = push_service.delete_subscription(
            tenant_id=tenant_id,
            employee_id=employee["id"],
            endpoint=payload.endpoint.strip(),
            conn=conn,
        )
    finally:
        conn.close()
    return {"ok": True, "removed": removed}
