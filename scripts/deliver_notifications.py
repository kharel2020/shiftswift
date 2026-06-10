#!/usr/bin/env python3
"""Deliver queued email/webhook/SMS notifications."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "backend_stub" / ".env"
sys.path.insert(0, str(ROOT / "backend_stub"))

if ENV_FILE.is_file():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if " #" in line:
            line = line.split(" #", 1)[0].rstrip()
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from core.notifications import process_queued_notifications  # noqa: E402


def main() -> int:
    import psycopg2

    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required")
    conn = psycopg2.connect(url)
    try:
        result = process_queued_notifications(conn=conn, limit=int(os.getenv("NOTIFICATION_BATCH_SIZE", "50")))
    finally:
        conn.close()
    print(json.dumps(result))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
