"""Local development login accounts — shiftswifthr.co.uk domain only."""

from __future__ import annotations

import os

from brand import EMAIL_ADMIN, EMAIL_EMPLOYEE, EMAIL_HR

# Legacy generic accounts removed on fresh seed (admin/admin, hr/hr, demo/demo).
LEGACY_USERNAMES: tuple[str, ...] = ("admin", "hr", "demo")

MASTER_USERNAME = os.getenv("DEV_MASTER_USERNAME", EMAIL_ADMIN)
MASTER_PASSWORD = os.getenv("DEV_MASTER_PASSWORD", "ShiftswiftHR-Platform-2026")
MASTER_ROLE = "admin"

TENANT_HR_USERNAME = os.getenv("DEV_TENANT_USERNAME", EMAIL_HR)
TENANT_HR_PASSWORD = os.getenv("DEV_TENANT_PASSWORD", "ShiftswiftHR-Tenant-2026")
TENANT_HR_ROLE = "hr"
TENANT_HR_TENANT_ID = 1

TENANT_EMPLOYEE_USERNAME = os.getenv("DEV_EMPLOYEE_USERNAME", EMAIL_EMPLOYEE)
TENANT_EMPLOYEE_PASSWORD = os.getenv("DEV_EMPLOYEE_PASSWORD", "ShiftswiftHR-Employee-2026")
TENANT_EMPLOYEE_ROLE = "employee"
TENANT_EMPLOYEE_TENANT_ID = 1


def master_tenant_id() -> int:
    return int(os.getenv("MASTER_CUSTOMER_ID", "999"))


def seeded_users() -> list[tuple[str, str, str, int]]:
    return [
        (MASTER_USERNAME, MASTER_PASSWORD, MASTER_ROLE, master_tenant_id()),
        (TENANT_HR_USERNAME, TENANT_HR_PASSWORD, TENANT_HR_ROLE, TENANT_HR_TENANT_ID),
        (
            TENANT_EMPLOYEE_USERNAME,
            TENANT_EMPLOYEE_PASSWORD,
            TENANT_EMPLOYEE_ROLE,
            TENANT_EMPLOYEE_TENANT_ID,
        ),
    ]


def development_fallback_users(*, master_tenant_id: str) -> dict[str, dict[str, str]]:
    return {
        MASTER_USERNAME: {
            "password": MASTER_PASSWORD,
            "role": MASTER_ROLE,
            "tenant_id": master_tenant_id,
        },
        TENANT_HR_USERNAME: {
            "password": TENANT_HR_PASSWORD,
            "role": TENANT_HR_ROLE,
            "tenant_id": str(TENANT_HR_TENANT_ID),
        },
        TENANT_EMPLOYEE_USERNAME: {
            "password": TENANT_EMPLOYEE_PASSWORD,
            "role": TENANT_EMPLOYEE_ROLE,
            "tenant_id": str(TENANT_EMPLOYEE_TENANT_ID),
        },
    }
