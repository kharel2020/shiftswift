#!/usr/bin/env python3
"""Test Brevo/SMTP settings from backend_stub/.env."""

from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "backend_stub" / ".env"
sys.path.insert(0, str(ROOT / "backend_stub"))


def load_env_file(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"Missing {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def main() -> int:
    load_env_file(ENV_FILE)

    host = os.getenv("SMTP_HOST", "")
    from_addr = os.getenv("SMTP_FROM", "")
    to_addr = (
        (sys.argv[1] if len(sys.argv) > 1 else "")
        or os.getenv("SMTP_TEST_TO", "")
        or os.getenv("EMAIL_SUPPORT", "")
        or os.getenv("SMTP_USER", "")
    )

    print(f"SMTP_HOST: {'set' if host else 'MISSING'}")
    print(f"SMTP_FROM: {from_addr or 'MISSING'}")
    print(f"SMTP_USER: {'set' if os.getenv('SMTP_USER') else 'MISSING'}")
    print(f"SMTP_PASSWORD: {'set' if os.getenv('SMTP_PASSWORD') else 'MISSING'}")

    if not host or not from_addr:
        print("\nFAIL: Set SMTP_HOST and SMTP_FROM in backend_stub/.env")
        return 1
    if not to_addr:
        print("\nFAIL: Pass recipient email or set EMAIL_SUPPORT / SMTP_TEST_TO")
        return 1

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_USE_TLS", "1").strip().lower() in {"1", "true", "yes"}

    from core.email_templates import render_email
    from core.notifications import format_from_header, format_reply_to_header, resolve_reply_to

    msg = EmailMessage()
    msg["Subject"] = "ShiftSwift HR — SMTP test"
    msg["From"] = format_from_header(audience="hr")
    msg["To"] = to_addr
    support = resolve_reply_to(audience="platform")
    if support:
        msg["Reply-To"] = format_reply_to_header(support)
    text = "If you received this message, ShiftSwift HR SMTP (Brevo) is configured correctly.\n"
    html = render_email(
        preheader="SMTP test successful",
        title="SMTP test successful",
        intro="If you can read this email, Brevo SMTP is working for ShiftSwift HR.",
        cta_url=os.getenv("APP_URL", "https://app.shiftswifthr.co.uk").rstrip("/") + "/business-login.html",
        cta_label="Open ShiftSwift HR",
    )
    msg.set_content(text, charset="utf-8")
    msg.add_alternative(html, subtype="html", charset="utf-8")

    print(f"\nConnecting to {host}:{port} ...")
    with smtplib.SMTP(host, port, timeout=30) as server:
        if use_tls:
            server.starttls()
        if user and password:
            server.login(user, password)
        server.send_message(msg)

    print(f"OK: test email sent to {to_addr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
