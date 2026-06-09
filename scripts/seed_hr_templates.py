#!/usr/bin/env python3
"""Seed HR templates from catalog and enable AI for demo tenant."""

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

from modules.hr_templates.sync import sync_all_templates

DATABASE_URL = os.getenv("DATABASE_URL")


def main() -> None:
    if not DATABASE_URL:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        summary = sync_all_templates(conn=conn)
        with conn.cursor() as cur:
            cur.execute("UPDATE tenants SET ai_assistant_enabled = TRUE WHERE id = 1")
        conn.commit()
    finally:
        conn.close()
    print(
        f"Seeded HR templates (created {summary['created']}, updated {summary['updated']}). "
        "AI enabled for demo tenant 1."
    )


if __name__ == "__main__":
    main()
