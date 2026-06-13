#!/usr/bin/env python3
"""Seed demo tenant with ShiftSwift HR branding for local fresh install."""

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

DATABASE_URL = os.getenv("DATABASE_URL")
DOMAIN = os.getenv("APP_DOMAIN", "shiftswifthr.co.uk")


def main() -> None:
    if not DATABASE_URL:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tenants SET
                  name = %s,
                  trading_name = %s,
                  registered_address = COALESCE(NULLIF(registered_address, ''), %s),
                  billing_email = %s,
                  signatory_name = %s,
                  signatory_title = %s,
                  signatory_email = %s,
                  subscription_plan = COALESCE(subscription_plan, 'site_medium_monthly'),
                  subscription_status = 'active',
                  trial_ends_at = NULL,
                  max_employees = COALESCE(max_employees, 25)
                WHERE id = 1
                """,
                (
                    "ShiftSwift HR Demo Tenant",
                    "ShiftSwift HR",
                    "1 Spinningfields, Manchester M3 3AP, United Kingdom",
                    f"billing@{DOMAIN}",
                    "HR Administrator",
                    "HR Director",
                    f"support@{DOMAIN}",
                ),
            )
        conn.commit()
    finally:
        conn.close()
    print(f"Seeded tenant branding for tenant 1 ({DOMAIN}) — demo tenant kept on active plan (no trial expiry).")


if __name__ == "__main__":
    main()
