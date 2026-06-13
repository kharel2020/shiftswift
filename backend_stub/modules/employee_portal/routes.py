"""Employee self-service — documents shared with the logged-in employee."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse

from auth_service import AuthUser
from config import load_settings
from core.database import get_connection
from deps import client_ip, get_employee_user, resolve_tenant_id
from modules.documents.constants import EMPLOYEE_DOCUMENT_CATEGORY_LABELS, EMPLOYEE_SELF_SERVICE_CATEGORIES
from modules.documents.service import get_employee_document, list_employee_documents
from modules.documents.storage import download_filename, resolve_stored_file
from modules.time_punch.service import resolve_employee

router = APIRouter(prefix="/employee/me", tags=["Employee self-service"])
settings = load_settings()


def _employee_for_user(*, tenant_id: int, user: AuthUser, conn: Any) -> dict[str, Any]:
    employee = resolve_employee(tenant_id=tenant_id, username=user.username, conn=conn)
    if not employee:
        raise HTTPException(
            status_code=404,
            detail="No employee record linked to this login — ask HR to add your work email to your employee profile.",
        )
    return employee


def _portal_document_row(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["id"],
        "title": doc["title"],
        "category": doc["category"],
        "category_label": EMPLOYEE_DOCUMENT_CATEGORY_LABELS.get(doc["category"], doc["category"]),
        "document_url": doc.get("document_url"),
        "has_file": doc.get("has_file"),
        "content_type": doc.get("content_type"),
        "original_filename": doc.get("original_filename"),
        "expires_at": doc.get("expires_at"),
        "pay_period": doc.get("pay_period"),
        "created_at": doc.get("created_at"),
    }


def _visible_portal_documents(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visible = []
    for doc in docs:
        if doc.get("category") not in EMPLOYEE_SELF_SERVICE_CATEGORIES:
            continue
        if not doc.get("has_file") and not doc.get("document_url"):
            continue
        visible.append(_portal_document_row(doc))
    return visible


@router.get("/documents")
def list_my_documents(
    current_user: Annotated[AuthUser, Depends(get_employee_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        employee = _employee_for_user(tenant_id=tenant_id, user=current_user, conn=conn)
        docs = list_employee_documents(tenant_id=tenant_id, employee_id=employee["id"], conn=conn)
        items = _visible_portal_documents(docs)
    finally:
        conn.close()
    return {
        "items": items,
        "count": len(items),
        "employee_name": f"{employee['first_name']} {employee['last_name']}".strip(),
    }


@router.get("/documents/{document_id}/file")
def download_my_document(
    document_id: int,
    current_user: Annotated[AuthUser, Depends(get_employee_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        employee = _employee_for_user(tenant_id=tenant_id, user=current_user, conn=conn)
        doc = get_employee_document(
            tenant_id=tenant_id,
            employee_id=employee["id"],
            document_id=document_id,
            conn=conn,
        )
    finally:
        conn.close()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.get("category") not in EMPLOYEE_SELF_SERVICE_CATEGORIES:
        raise HTTPException(status_code=403, detail="This document is not shared in the employee portal")
    if not doc.get("storage_path"):
        raise HTTPException(status_code=404, detail="No file stored for this document")
    path = resolve_stored_file(tenant_id=tenant_id, storage_path=doc.get("storage_path"))
    filename = download_filename(
        title=str(doc.get("title") or "document"),
        original_filename=doc.get("original_filename"),
        storage_path=doc.get("storage_path"),
    )
    return FileResponse(
        path,
        media_type=doc.get("content_type") or "application/octet-stream",
        filename=filename,
    )


@router.get("/notes")
def list_my_notes(
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_employee_user)],
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> dict[str, object]:
    from modules.employee_notes.service import list_notes_for_employee

    tenant_id = resolve_tenant_id(current_user, x_tenant_id, settings=settings)
    conn = get_connection()
    try:
        employee = _employee_for_user(tenant_id=tenant_id, user=current_user, conn=conn)
        items = list_notes_for_employee(
            tenant_id=tenant_id,
            employee_id=int(employee["id"]),
            actor_username=current_user.username,
            actor_role=current_user.role,
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            conn=conn,
        )
    finally:
        conn.close()
    return {"items": items, "count": len(items)}

