#!/usr/bin/env python3
"""Seed bcrypt-hashed local dev users (@shiftswifthr.co.uk). Removes legacy generic accounts."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend_stub"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend_stub" / ".env")
load_dotenv(ROOT / ".env")

import psycopg2

from auth_service import hash_password
from dev_credentials import LEGACY_USERNAMES, master_tenant_id, seeded_users

DATABASE_URL = os.getenv("DATABASE_URL")


def main() -> None:
    if not DATABASE_URL:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    users = seeded_users()
    platform_tenant_id = master_tenant_id()
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name, subscription_status, subscription_plan, max_employees)
                VALUES (%s, 'ShiftSwift HR Platform', 'active', 'site_medium_monthly', 999)
                ON CONFLICT (id) DO NOTHING
                """,
                (platform_tenant_id,),
            )
            cur.execute(
                "SELECT setval(pg_get_serial_sequence('tenants', 'id'), GREATEST((SELECT MAX(id) FROM tenants), 1))"
            )
            cur.execute(
                "DELETE FROM app_users WHERE lower(username) = ANY(%s)",
                ([name.lower() for name in LEGACY_USERNAMES],),
            )
            for username, password, role, tenant_id in users:
                login_portal = "master" if role == "admin" else "business"
                cur.execute(
                    """
                    INSERT INTO app_users (username, password_hash, role, tenant_id, login_portal)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (username) DO UPDATE SET
                      password_hash = EXCLUDED.password_hash,
                      role = EXCLUDED.role,
                      tenant_id = EXCLUDED.tenant_id,
                      login_portal = EXCLUDED.login_portal,
                      is_active = TRUE,
                      updated_at = NOW()
                    """,
                    (username, hash_password(password), role, tenant_id, login_portal),
                )
        conn.commit()
    finally:
        conn.close()

    tenant_user = users[1]
    employee_user = users[2]
    master_user = users[0]
    print(
        "Seeded app_users:\n"
        f"  Master admin (tenant {master_user[3]}): {master_user[0]}\n"
        f"  Business HR (business {tenant_user[3]}): {tenant_user[0]}\n"
        f"  Employee (business {employee_user[3]}): {employee_user[0]}\n"
        "Removed legacy accounts: admin, hr, demo.\n"
        "Change DEV_* passwords before production."
    )


if __name__ == "__main__":
    main()
