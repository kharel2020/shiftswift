#!/usr/bin/env python3
"""Diagnose SMTP config and recent notification delivery on the server."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "backend_stub" / ".env"
sys.path.insert(0, str(ROOT / "backend_stub"))


def load_env() -> None:
    if not ENV_FILE.is_file():
        raise SystemExit(f"Missing {ENV_FILE}")
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if " #" in line:
            line = line.split(" #", 1)[0].rstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def main() -> int:
    load_env()
    from core.notifications import smtp_config_summary

    print("=== SMTP configuration (from backend_stub/.env) ===")
    summary = smtp_config_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    url = os.getenv("DATABASE_URL")
    if not url:
        print("\nDATABASE_URL missing — cannot inspect notifications table")
        return 1

    import psycopg2

    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, tenant_id, subject, status, payload, created_at
                FROM notifications
                WHERE channel = 'email'
                ORDER BY created_at DESC
                LIMIT 15
                """
            )
            rows = cur.fetchall()
        print(f"\n=== Last {len(rows)} email notifications ===")
        if not rows:
            print("  (none — try signup or forgot-password, then run this again)")
        for row in rows:
            notif_id, tenant_id, subject, status, payload_raw, created_at = row
            payload = payload_raw if isinstance(payload_raw, dict) else json.loads(payload_raw or "{}")
            to_addr = payload.get("to", "?")
            err = payload.get("delivery_error", "")
            print(f"  #{notif_id} [{created_at}] {status} → {to_addr}")
            print(f"    {subject[:70]}")
            if err:
                print(f"    error: {err}")
    finally:
        conn.close()

    if not summary["configured"]:
        print("\nFAIL: SMTP incomplete in .env")
        return 1

    if len(sys.argv) > 1 and sys.argv[1] == "--send-test":
        recipient = sys.argv[2] if len(sys.argv) > 2 else os.getenv("EMAIL_SUPPORT", "")
        if not recipient:
            print("Usage: diagnose_email.py --send-test you@email.com")
            return 1
        print(f"\n=== Sending SMTP test to {recipient} ===")
        import subprocess

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "test_smtp.py"), recipient],
            cwd=str(ROOT),
            check=False,
        )
        return result.returncode

    print("\nTip: run with --send-test you@email.com to send a live SMTP test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
