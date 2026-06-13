"""Branded HTML + plain-text email templates for ShiftSwift HR."""

from __future__ import annotations

import html
import os
from dataclasses import dataclass
from typing import Iterable

APP_NAME = os.getenv("APP_NAME", "ShiftSwift HR")
APP_DOMAIN = os.getenv("APP_DOMAIN", "shiftswifthr.co.uk")
APP_URL = os.getenv("APP_URL", f"https://app.{APP_DOMAIN}").rstrip("/")
MARKETING_URL = os.getenv("MARKETING_URL", f"https://www.{APP_DOMAIN}").rstrip("/")
SUPPORT_EMAIL = os.getenv("EMAIL_SUPPORT", f"support@{APP_DOMAIN}")
LOGO_URL = os.getenv(
    "EMAIL_LOGO_URL",
    f"{APP_URL}/assets/shiftswift-hr-logo.png",
)

# Brand kit colours (inline for email clients)
GREEN_900 = "#04342c"
GREEN_800 = "#085041"
GREEN_700 = "#0f6e56"
GREEN_500 = "#1d9e75"
GREEN_100 = "#e1f5ee"
PAGE_BG = "#f5f4f0"
INK = "#111111"
MUTED = "#5f5e5a"
BORDER = "#d3d1c7"


@dataclass(frozen=True)
class EmailContent:
    subject: str
    text: str
    html: str


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _paragraphs(text_blocks: Iterable[str]) -> str:
    return "".join(
        f'<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:{INK};">{_esc(block)}</p>'
        for block in text_blocks
    )


def _bullet_list(items: Iterable[tuple[str, str]]) -> str:
    rows = []
    for label, value in items:
        rows.append(
            f'<tr>'
            f'<td style="padding:8px 0;color:{MUTED};font-size:14px;width:120px;vertical-align:top;">{_esc(label)}</td>'
            f'<td style="padding:8px 0;color:{INK};font-size:14px;font-weight:600;">{_esc(value)}</td>'
            f"</tr>"
        )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin:0 0 20px;background:{GREEN_100};border-radius:12px;padding:4px 16px;">'
        f"{''.join(rows)}</table>"
    )


def _cta_button(url: str, label: str) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0 8px;">'
        f"<tr><td>"
        f'<a href="{_esc(url)}" style="display:inline-block;background:{GREEN_700};color:#ffffff;'
        f"text-decoration:none;font-size:15px;font-weight:700;padding:14px 28px;border-radius:10px;"
        f'font-family:Segoe UI,Helvetica,Arial,sans-serif;">{_esc(label)}</a>'
        f"</td></tr></table>"
    )


def render_email(
    *,
    preheader: str,
    title: str,
    intro: str,
    paragraphs: Iterable[str] = (),
    details: Iterable[tuple[str, str]] = (),
    cta_url: str | None = None,
    cta_label: str | None = None,
    footer_note: str | None = None,
) -> str:
    """Wrap content in a responsive, client-safe HTML shell."""
    preheader_esc = _esc(preheader)
    detail_html = _bullet_list(details) if details else ""
    cta_html = _cta_button(cta_url, cta_label) if cta_url and cta_label else ""
    footer = footer_note or f"Questions? Reply to {_esc(SUPPORT_EMAIL)}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light" />
  <meta name="supported-color-schemes" content="light" />
  <title>{_esc(title)}</title>
  <style>
    @media only screen and (max-width: 620px) {{
      .shell {{ width: 100% !important; }}
      .pad {{ padding-left: 20px !important; padding-right: 20px !important; }}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background:{PAGE_BG};font-family:'Segoe UI',Helvetica,Arial,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{preheader_esc}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAGE_BG};">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" class="shell" width="600" cellpadding="0" cellspacing="0"
          style="max-width:600px;width:100%;background:#ffffff;border:1px solid {BORDER};border-radius:16px;overflow:hidden;">
          <tr>
            <td style="background:linear-gradient(135deg,{GREEN_800},{GREEN_700});padding:24px 28px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="vertical-align:middle;">
                    <img src="{_esc(LOGO_URL)}" alt="{_esc(APP_NAME)}" width="160"
                      style="display:block;max-width:160px;height:auto;border:0;" />
                  </td>
                  <td align="right" style="vertical-align:middle;color:#ffffff;font-size:12px;opacity:0.9;">
                    UK HR &amp; compliance
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td class="pad" style="padding:32px 28px 12px;">
              <h1 style="margin:0 0 12px;font-size:22px;line-height:1.3;color:{GREEN_900};">{_esc(title)}</h1>
              <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:{INK};">{_esc(intro)}</p>
              {_paragraphs(paragraphs)}
              {detail_html}
              {cta_html}
            </td>
          </tr>
          <tr>
            <td class="pad" style="padding:8px 28px 28px;">
              <p style="margin:0 0 8px;font-size:13px;line-height:1.5;color:{MUTED};">{_esc(footer)}</p>
              <p style="margin:0;font-size:12px;line-height:1.5;color:{MUTED};">
                {_esc(APP_NAME)} · {_esc(APP_DOMAIN)}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def welcome_trial_email(
    *,
    business_name: str,
    billing_email: str,
    plan_name: str,
    trial_days: int,
) -> EmailContent:
    login_url = f"{APP_URL}/business-login.html"
    subject = f"Welcome to {APP_NAME} — your {trial_days}-day trial is active"
    text = (
        f"Hello,\n\n"
        f"Your {APP_NAME} workspace for {business_name} is ready.\n\n"
        f"Sign in: {login_url}\n"
        f"Username: {billing_email}\n"
        f"Plan: {plan_name}\n"
        f"Trial: {trial_days} days\n\n"
        f"Need help? Reply to {SUPPORT_EMAIL}\n\n"
        f"{APP_NAME}\n"
    )
    html = render_email(
        preheader=f"Your {trial_days}-day trial for {business_name} is ready.",
        title=f"Your {trial_days}-day trial is active",
        intro=f"Your {APP_NAME} workspace for {business_name} is ready. Sign in below to set up HR, compliance, and your team.",
        details=[
            ("Username", billing_email),
            ("Plan", plan_name),
            ("Trial", f"{trial_days} days"),
        ],
        cta_url=login_url,
        cta_label="Open HR dashboard",
    )
    return EmailContent(subject=subject, text=text, html=html)


def password_reset_email(*, role_label: str, reset_url: str, reset_hours: int) -> EmailContent:
    subject = f"{APP_NAME} — reset your password"
    text = (
        f"Hello,\n\n"
        f"We received a request to reset the password for your {APP_NAME} {role_label} account.\n\n"
        f"Open this link to choose a new password (expires in {reset_hours} hours):\n"
        f"{reset_url}\n\n"
        f"If you did not request this, you can ignore this email.\n\n"
        f"{APP_NAME}\n"
        f"Reply: {SUPPORT_EMAIL}\n"
    )
    html = render_email(
        preheader="Reset your ShiftSwift HR password.",
        title="Reset your password",
        intro=f"We received a request to reset the password for your {role_label} account.",
        paragraphs=[
            f"This link expires in {reset_hours} hours. If you did not request a reset, you can ignore this email.",
        ],
        cta_url=reset_url,
        cta_label="Choose a new password",
    )
    return EmailContent(subject=subject, text=text, html=html)


def contract_signing_email(
    *,
    signatory_name: str | None,
    contract_name: str,
    contract_number: str,
    signing_url: str,
) -> EmailContent:
    greeting = signatory_name or "there"
    subject = f"{APP_NAME} — Please sign {contract_name} ({contract_number})"
    text = (
        f"Dear {greeting},\n\n"
        f"Please review and sign your ShiftSwift HR legal agreement:\n{signing_url}\n\n"
        f"This link expires in 30 days.\n\n{APP_NAME}\n"
    )
    html = render_email(
        preheader=f"Sign your {contract_name}.",
        title="Please review and sign",
        intro=f"Dear {greeting}, your {contract_name} ({contract_number}) is ready for electronic signature.",
        paragraphs=["This secure link expires in 30 days."],
        cta_url=signing_url,
        cta_label="Review and sign",
    )
    return EmailContent(subject=subject, text=text, html=html)


def trial_reminder_email(
    *,
    tenant_name: str,
    days_left: int | None,
    trial_end_label: str,
    reminder_key: str,
    upgrade_url: str,
) -> EmailContent:
    if reminder_key == "expired":
        subject = f"{APP_NAME} — your free trial has ended"
        intro = f"Your 14-day trial for {tenant_name} ended on {trial_end_label}."
        preheader = "Upgrade to keep access to ShiftSwift HR."
        paragraphs = [
            "Upgrade now to keep HR records, sponsor compliance alerts, templates, and payroll add-ons.",
        ]
        cta_label = "Upgrade your plan"
    else:
        day_word = "day" if days_left == 1 else "days"
        subject = f"{APP_NAME} — {days_left} {day_word} left on your free trial"
        intro = f"Your trial for {tenant_name} ends on {trial_end_label} ({days_left} {day_word} remaining)."
        preheader = f"{days_left} {day_word} left on your ShiftSwift HR trial."
        paragraphs = [
            "Upgrade before the trial ends to avoid interruption. All prices are shown ex VAT.",
        ]
        cta_label = "Upgrade before trial ends"

    text = f"Hello,\n\n{intro}\n\n{upgrade_url}\n\nQuestions? Reply to support@{APP_DOMAIN}\n\n— {APP_NAME}\n"
    html = render_email(
        preheader=preheader,
        title=subject.replace(f"{APP_NAME} — ", ""),
        intro=intro,
        paragraphs=paragraphs,
        cta_url=upgrade_url,
        cta_label=cta_label,
    )
    return EmailContent(subject=subject, text=text, html=html)


def compliance_alert_email(*, message: str) -> EmailContent:
    subject = f"{APP_NAME}: Compliance action required"
    text = f"{message}\n\n— {APP_NAME}\n"
    html = render_email(
        preheader="Compliance action required in ShiftSwift HR.",
        title="Compliance action required",
        intro=message,
        cta_url=f"{APP_URL}/admin.html#compliance",
        cta_label="Open compliance dashboard",
    )
    return EmailContent(subject=subject, text=text, html=html)


def employee_document_shared_email(
    *,
    employee_name: str,
    document_title: str,
    category_label: str,
    pay_period: str | None,
    tenant_name: str,
) -> EmailContent:
    period_line = f" for {pay_period}" if pay_period else ""
    subject = f"{APP_NAME} — New {category_label.lower()}{period_line}"
    portal_url = f"{APP_URL}/employee.html#documents"
    intro = f"{tenant_name} has shared a new document with you: {document_title}."
    details = [("Type", category_label)]
    if pay_period:
        details.append(("Pay period", pay_period))
    text = (
        f"Hello {employee_name},\n\n"
        f"{intro}\n\n"
        f"Sign in to your employee portal to view and download it:\n{portal_url}\n\n"
        f"— {APP_NAME}\n"
    )
    html = render_email(
        preheader=f"New {category_label.lower()} from {tenant_name}.",
        title="New document available",
        intro=f"Hello {employee_name}, {intro}",
        details=details,
        cta_url=portal_url,
        cta_label="Open employee portal",
    )
    return EmailContent(subject=subject, text=text, html=html)


def rota_published_email(
    *,
    employee_name: str,
    tenant_name: str,
    week_label: str,
    shift_lines: list[str],
) -> EmailContent:
    subject = f"{APP_NAME} — Your rota for {week_label}"
    portal_url = f"{APP_URL}/employee.html#rota"
    shift_text = "\n".join(f"• {line}" for line in shift_lines) if shift_lines else "See your employee portal for details."
    intro = f"{tenant_name} has published your shifts for {week_label}."
    text = (
        f"Hello {employee_name},\n\n"
        f"{intro}\n\n"
        f"{shift_text}\n\n"
        f"View your full rota:\n{portal_url}\n\n"
        f"— {APP_NAME}\n"
    )
    paragraphs = shift_lines[:8] if shift_lines else ["Open your employee portal to see your full schedule."]
    if len(shift_lines) > 8:
        paragraphs.append(f"…and {len(shift_lines) - 8} more shift(s) in the portal.")
    html = render_email(
        preheader=f"Your rota for {week_label} is ready.",
        title="Your rota is published",
        intro=f"Hello {employee_name}, {intro}",
        paragraphs=paragraphs,
        cta_url=portal_url,
        cta_label="View my rota",
    )
    return EmailContent(subject=subject, text=text, html=html)


def payment_failure_email(
    *,
    tenant_name: str,
    reminder_key: str,
    billing_url: str,
    grace_days_left: int | None = None,
    grace_period_days: int = 14,
) -> EmailContent:
    domain = APP_DOMAIN
    if reminder_key == "grace_start":
        subject = f"{APP_NAME} — payment failed"
        intro = f"We could not collect your subscription payment by Direct Debit for {tenant_name}."
        paragraphs = [
            f"You have {grace_period_days} days to resolve this before your software licence is placed on hold.",
            "Update your payment details or pay now using the button below.",
        ]
    elif reminder_key == "grace_mid":
        subject = f"{APP_NAME} — payment still overdue"
        intro = "Your Direct Debit payment for ShiftSwift HR is still outstanding."
        paragraphs = [
            f"Grace period remaining: {grace_days_left} day(s). After that, access will be restricted.",
        ]
    elif reminder_key == "grace_1_day":
        subject = f"{APP_NAME} — licence will be placed on hold tomorrow"
        intro = "This is your final reminder before your licence is placed on hold."
        paragraphs = ["Pay or update Direct Debit within 1 day to keep uninterrupted access."]
    else:
        subject = f"{APP_NAME} — software licence on hold"
        intro = f"Your licence is on hold because we have not received payment after the {grace_period_days}-day grace period."
        paragraphs = ["Admin access is restricted until payment succeeds."]

    text = f"Hello,\n\n{intro}\n\n{billing_url}\n\nSupport: support@{domain}\n\n— {APP_NAME}\n"
    html = render_email(
        preheader=subject,
        title=subject.replace(f"{APP_NAME} — ", ""),
        intro=intro,
        paragraphs=paragraphs,
        cta_url=billing_url,
        cta_label="Resolve payment",
    )
    return EmailContent(subject=subject, text=text, html=html)


def generic_notification_email(*, subject: str, message: str, cta_url: str | None = None, cta_label: str | None = None) -> EmailContent:
    """Fallback HTML wrapper for legacy plain-text notifications."""
    text = f"{message}\n\n— {APP_NAME}\n"
    html = render_email(
        preheader=subject,
        title=subject,
        intro=message,
        cta_url=cta_url,
        cta_label=cta_label,
    )
    return EmailContent(subject=subject, text=text, html=html)
