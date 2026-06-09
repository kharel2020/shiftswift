#!/usr/bin/env python3
"""Seed contract template registry."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend_stub"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend_stub" / ".env")

import psycopg2

from contracts_service import seed_templates

DATABASE_URL = os.getenv("DATABASE_URL")


def main() -> None:
    if not DATABASE_URL:
        print("DATABASE_URL required", file=sys.stderr)
        sys.exit(1)
    conn = psycopg2.connect(DATABASE_URL)
    try:
        seed_templates(conn)
        conn.commit()
    finally:
        conn.close()
    print("Seeded contract_templates (msa, dpa, subscription_order).")


if __name__ == "__main__":
    main()
