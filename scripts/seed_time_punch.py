#!/usr/bin/env python3
"""Seed demo punch site, employee record, and assignment for local dev."""

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

from brand import EMAIL_EMPLOYEE
from dev_credentials import TENANT_EMPLOYEE_USERNAME
from modules.time_punch.service import assign_employee_to_site, upsert_primary_punch_site

DATABASE_URL = os.getenv("DATABASE_URL")
TENANT_ID = 1
DEMO_ADDRESS = "1 Spinningfields, Manchester M3 3AP, United Kingdom"
DEMO_LAT = 53.4794
DEMO_LNG = -2.2451


def main() -> None:
    if not DATABASE_URL:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tenants SET registered_address = %s
                WHERE id = %s AND (registered_address IS NULL OR registered_address = '')
                """,
                (DEMO_ADDRESS, TENANT_ID),
            )
        conn.commit()

        site = upsert_primary_punch_site(
            tenant_id=TENANT_ID,
            name="ShiftSwift HR — main",
            address=DEMO_ADDRESS,
            latitude=DEMO_LAT,
            longitude=DEMO_LNG,
            radius_meters=150,
            conn=conn,
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM employees
                WHERE tenant_id = %s AND lower(email) = lower(%s)
                LIMIT 1
                """,
                (TENANT_ID, EMAIL_EMPLOYEE),
            )
            row = cur.fetchone()
            if row:
                employee_id = row[0]
            else:
                cur.execute(
                    """
                    INSERT INTO employees (
                      tenant_id, first_name, last_name, email, job_title, status, work_location
                    )
                    VALUES (%s, %s, %s, %s, %s, 'active', %s)
                    RETURNING id
                    """,
                    (TENANT_ID, "Demo", "Employee", EMAIL_EMPLOYEE, "Team Member", DEMO_ADDRESS),
                )
                employee_id = cur.fetchone()[0]
                conn.commit()

        assign_employee_to_site(
            tenant_id=TENANT_ID,
            employee_id=employee_id,
            punch_site_id=site["id"],
            conn=conn,
        )
    finally:
        conn.close()

    print(
        "Seeded time punch demo:\n"
        f"  Site: {site['name']} ({DEMO_LAT}, {DEMO_LNG}) radius {site['radius_meters']}m\n"
        f"  Employee login: {TENANT_EMPLOYEE_USERNAME} → employee id {employee_id}\n"
        "  Punch within ~150m of Manchester Spinningfields to clock in/out."
    )


if __name__ == "__main__":
    main()
