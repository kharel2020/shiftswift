#!/usr/bin/env python3
"""Sync HR process templates from platform catalog (run after law/guidance updates)."""

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
    finally:
        conn.close()

    print(
        f"HR template sync complete — created: {summary['created']}, "
        f"updated: {summary['updated']}, unchanged: {summary['unchanged']}"
    )
    for item in summary["templates"]:
        if item["status"] != "unchanged":
            print(f"  · {item['id']} v{item['version']} — {item['status']}")


if __name__ == "__main__":
    main()
