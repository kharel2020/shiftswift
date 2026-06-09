"""Domain events and webhook subscription routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from auth_service import AuthUser
from config import load_settings
from core.database import get_connection
from core.events import process_pending_events
from core.permissions import check_permission
from deps import get_hr_user, resolve_tenant_id

router = APIRouter(prefix="/events", tags=["Domain Events & Webhooks"])
settings = load_settings()


class WebhookSubscriptionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    target_url: str = Field(min_length=8, max_length=2048)
    event_types: list[str] = Field(default_factory=list)
    secret: str | None = Field(default=None, max_length=128)


@router.get("/subscriptions")
def list_subscriptions(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "settings.read")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, target_url, event_types, is_active, created_at
                FROM webhook_subscriptions WHERE tenant_id = %s ORDER BY created_at DESC
                """,
                (tenant_id,),
            )
            items = [
                {
                    "id": row[0],
                    "name": row[1],
                    "target_url": row[2],
                    "event_types": list(row[3] or []),
                    "is_active": row[4],
                    "created_at": row[5].isoformat() if row[5] else None,
                }
                for row in cur.fetchall()
            ]
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.post("/subscriptions")
def create_subscription(
    payload: WebhookSubscriptionCreate,
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    check_permission(current_user, "settings.write")
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO webhook_subscriptions (tenant_id, name, target_url, event_types, secret)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, name, target_url, event_types, is_active
                """,
                (tenant_id, payload.name, payload.target_url, payload.event_types, payload.secret),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    return {
        "id": row[0],
        "name": row[1],
        "target_url": row[2],
        "event_types": list(row[3] or []),
        "is_active": row[4],
    }


@router.post("/process-pending")
def process_pending(
    current_user: Annotated[AuthUser, Depends(get_hr_user)],
) -> dict[str, object]:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    conn = get_connection()
    try:
        count = process_pending_events(conn=conn)
    finally:
        conn.close()
    return {"processed": count}
