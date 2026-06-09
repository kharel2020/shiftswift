"""RBAC permission checks for module routes."""

from __future__ import annotations

from fastapi import HTTPException

from auth_service import AuthUser
from rbac import has_permission, normalize_role


def check_permission(user: AuthUser, permission: str) -> None:
    role = normalize_role(user.role)
    if user.role == "admin":
        return
    if not has_permission(role, permission):
        raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
