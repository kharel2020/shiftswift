"""Document store export — CSV manifest and ZIP archive."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, datetime
from typing import Any

from modules.documents.storage import document_has_file, resolve_rtw_file, resolve_stored_file


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


CSV_COLUMNS = [
    "scope",
    "id",
    "employee_id",
    "title",
    "category",
    "lifecycle_stage",
    "document_url",
    "has_file",
    "content_sha256",
    "content_type",
    "file_size_bytes",
    "original_filename",
    "expires_at",
    "uploaded_by",
    "created_at",
    "notes",
]


def build_documents_csv(
    *,
    tenant_id: int,
    tenant_documents: list[dict[str, Any]],
    employee_documents: list[dict[str, Any]],
) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for doc in tenant_documents:
        writer.writerow(
            {
                "scope": "tenant",
                "id": doc.get("id"),
                "employee_id": doc.get("employee_id") or "",
                "title": doc.get("title"),
                "category": doc.get("category"),
                "lifecycle_stage": doc.get("lifecycle_stage"),
                "document_url": doc.get("document_url") or "",
                "has_file": "yes" if document_has_file(doc) else "no",
                "content_sha256": doc.get("content_sha256") or "",
                "content_type": doc.get("content_type") or "",
                "file_size_bytes": doc.get("file_size_bytes") or "",
                "original_filename": doc.get("original_filename") or "",
                "expires_at": _iso(doc.get("expires_at")),
                "uploaded_by": doc.get("uploaded_by") or "",
                "created_at": _iso(doc.get("created_at")),
                "notes": (doc.get("notes") or "").replace("\n", " "),
            }
        )
    for doc in employee_documents:
        writer.writerow(
            {
                "scope": "employee",
                "id": doc.get("id"),
                "employee_id": doc.get("employee_id"),
                "title": doc.get("title"),
                "category": doc.get("category"),
                "lifecycle_stage": doc.get("lifecycle_stage"),
                "document_url": doc.get("document_url") or "",
                "has_file": "yes" if document_has_file(doc) else "no",
                "content_sha256": doc.get("content_sha256") or "",
                "content_type": doc.get("content_type") or "",
                "file_size_bytes": doc.get("file_size_bytes") or "",
                "original_filename": doc.get("original_filename") or "",
                "expires_at": _iso(doc.get("expires_at")),
                "uploaded_by": doc.get("uploaded_by") or "",
                "created_at": _iso(doc.get("created_at")),
                "notes": (doc.get("notes") or "").replace("\n", " "),
            }
        )
    return buffer.getvalue()


def _zip_entry_name(*, scope: str, doc: dict[str, Any], path_prefix: str) -> str:
    employee_id = doc.get("employee_id")
    title = str(doc.get("title") or "document").replace("/", "-")
    doc_id = doc.get("id")
    original = doc.get("original_filename")
    if original:
        suffix = original
    else:
        suffix = f"{doc_id}_{title}"
    if scope == "employee":
        return f"{path_prefix}employees/{employee_id}/{suffix}"
    return f"{path_prefix}tenant/{suffix}"


def build_documents_zip(
    *,
    tenant_id: int,
    tenant_documents: list[dict[str, Any]],
    employee_documents: list[dict[str, Any]],
    rtw_checks: list[dict[str, Any]] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.csv",
            build_documents_csv(
                tenant_id=tenant_id,
                tenant_documents=tenant_documents,
                employee_documents=employee_documents,
            ),
        )
        for doc in tenant_documents:
            if not document_has_file(doc):
                continue
            path = resolve_stored_file(tenant_id=tenant_id, storage_path=doc.get("storage_path"))
            archive.write(path, _zip_entry_name(scope="tenant", doc=doc, path_prefix="files/"))
        for doc in employee_documents:
            if not document_has_file(doc):
                continue
            path = resolve_stored_file(tenant_id=tenant_id, storage_path=doc.get("storage_path"))
            archive.write(path, _zip_entry_name(scope="employee", doc=doc, path_prefix="files/"))
        for check in rtw_checks or []:
            if not check.get("storage_path"):
                continue
            path = resolve_rtw_file(tenant_id=tenant_id, storage_path=check.get("storage_path"))
            employee_id = check.get("employee_id")
            check_id = check.get("id")
            check_date = check.get("check_date") or "unknown-date"
            archive.write(
                path,
                f"files/rtw/{employee_id}/rtw-check-{check_id}_{check_date}.pdf",
            )
    return buffer.getvalue()
