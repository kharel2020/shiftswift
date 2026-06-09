"""14-day software trial — reminders, expiry, and upgrade checkout."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from billing_config import stripe_settings
from billing_plans import get_plan, resolve_stripe_price_id
from billing_stripe_checkout import create_subscription_checkout_session
from payroll_plans import get_payroll_plan, resolve_stripe_price_id as resolve_payroll_stripe_price_id

DEFAULT_TRIAL_DAYS = int(os.getenv("BILLING_TRIAL_DAYS", "14"))
ACTIVE_STATUSES = frozenset({"active", "paid"})
TRIALING_STATUSES = frozenset({"trialing", "provisioning"})
REMINDER_KEYS = ("7_day", "3_day", "1_day", "expired")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _app_url() -> str:
    return os.getenv("APP_URL", os.getenv("LOCAL_APP_URL", "http://localhost:5173")).rstrip("/")


def _upgrade_page_url() -> str:
    return os.getenv("BILLING_UPGRADE_URL", f"{_app_url()}/admin.html#payroll")


def days_until_trial_end(*, trial_ends_at: datetime | None, as_of: datetime | None = None) -> int | None:
    if not trial_ends_at:
        return None
    now = as_of or _utcnow()
    if trial_ends_at.tzinfo is None:
        trial_ends_at = trial_ends_at.replace(tzinfo=timezone.utc)
    return (trial_ends_at.date() - now.date()).days


def fetch_tenant_billing_row(cur: Any, tenant_id: int) -> tuple[Any, ...] | None:
    cur.execute(
        """
        SELECT id, name, billing_email, subscription_plan, subscription_status,
               trial_ends_at, stripe_customer_id, stripe_subscription_id,
               payroll_plan_id, payroll_enabled, max_employees
        FROM tenants
        WHERE id = %s
        """,
        (tenant_id,),
    )
    return cur.fetchone()


def trial_snapshot(*, tenant_id: int, conn: Any, as_of: datetime | None = None) -> dict[str, Any]:
    now = as_of or _utcnow()
    with conn.cursor() as cur:
        row = fetch_tenant_billing_row(cur, tenant_id)
    if not row:
        raise LookupError("tenant not found")

    (
        _tid,
        name,
        billing_email,
        plan_id,
        status,
        trial_ends_at,
        stripe_customer_id,
        stripe_subscription_id,
        payroll_plan_id,
        payroll_enabled,
        max_employees,
    ) = row

    days_left = days_until_trial_end(trial_ends_at=trial_ends_at, as_of=now)
    is_active = status in ACTIVE_STATUSES
    is_trialing = status in TRIALING_STATUSES
    trial_expired = status == "trial_expired" or (
        is_trialing and days_left is not None and days_left < 0
    )
    access_allowed = is_active or (is_trialing and not trial_expired)
    upgrade_required = trial_expired or (is_trialing and days_left is not None and days_left <= 0)

    return {
        "tenant_id": tenant_id,
        "tenant_name": name,
        "billing_email": billing_email,
        "subscription_plan": plan_id,
        "subscription_status": status,
        "trial_days_default": DEFAULT_TRIAL_DAYS,
        "trial_ends_at": trial_ends_at.isoformat() if isinstance(trial_ends_at, datetime) else trial_ends_at,
        "days_remaining": max(days_left, 0) if days_left is not None else None,
        "is_trialing": is_trialing,
        "is_active": is_active,
        "trial_expired": trial_expired,
        "upgrade_required": upgrade_required,
        "access_allowed": access_allowed,
        "upgrade_url": _upgrade_page_url(),
        "stripe_customer_id": stripe_customer_id,
        "stripe_subscription_id": stripe_subscription_id,
        "payroll_plan_id": payroll_plan_id,
        "payroll_enabled": bool(payroll_enabled),
        "max_employees": max_employees,
    }


def ensure_tenant_trial_started(*, tenant_id: int, conn: Any) -> None:
    """Set trial_ends_at for trialing tenants missing a clock (e.g. legacy rows)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tenants
            SET trial_ends_at = NOW() + (%s || ' days')::INTERVAL,
                subscription_status = CASE
                  WHEN subscription_status IN ('active', 'cancelled', 'trial_expired') THEN subscription_status
                  ELSE 'trialing'
                END
            WHERE id = %s
              AND trial_ends_at IS NULL
              AND subscription_status NOT IN ('active', 'cancelled')
            """,
            (DEFAULT_TRIAL_DAYS, tenant_id),
        )


def _reminder_already_sent(cur: Any, tenant_id: int, reminder_key: str) -> bool:
    cur.execute(
        "SELECT 1 FROM trial_reminder_log WHERE tenant_id = %s AND reminder_key = %s",
        (tenant_id, reminder_key),
    )
    return cur.fetchone() is not None


def _log_reminder(cur: Any, tenant_id: int, reminder_key: str) -> None:
    cur.execute(
        """
        INSERT INTO trial_reminder_log (tenant_id, reminder_key)
        VALUES (%s, %s)
        ON CONFLICT (tenant_id, reminder_key) DO NOTHING
        """,
        (tenant_id, reminder_key),
    )


def _queue_trial_email(
    cur: Any,
    *,
    tenant_id: int,
    to_email: str,
    subject: str,
    body: str,
    reminder_key: str,
) -> None:
    cur.execute(
        """
        INSERT INTO notifications (tenant_id, channel, subject, body, payload, status)
        VALUES (%s, 'email', %s, %s, %s::jsonb, 'queued')
        """,
        (
            tenant_id,
            subject,
            body,
            json.dumps({"to": to_email, "reminder_key": reminder_key, "type": "trial_upgrade", "purpose": "billing"}),
        ),
    )
    _log_reminder(cur, tenant_id, reminder_key)


def _email_body(
    *,
    tenant_name: str,
    days_left: int | None,
    trial_ends_at: datetime | None,
    reminder_key: str,
) -> tuple[str, str]:
    upgrade_url = _upgrade_page_url()
    end_label = trial_ends_at.date().isoformat() if isinstance(trial_ends_at, datetime) else "soon"
    brand = "ShiftSwift HR"
    domain = os.getenv("APP_DOMAIN", "shiftswifthr.co.uk")

    if reminder_key == "expired":
        subject = f"{brand} — your free trial has ended · upgrade to continue"
        body = f"""Hello,

Your 14-day {brand} trial for {tenant_name} ended on {end_label}.

Upgrade now to keep access to HR records, sponsor compliance alerts, templates, and payroll add-ons:

{upgrade_url}

Questions? Reply to support@{domain}

— {brand} · {domain}
"""
        return subject, body

    day_word = "day" if days_left == 1 else "days"
    subject = f"{brand} — {days_left} {day_word} left on your free trial"
    body = f"""Hello,

Your {brand} trial for {tenant_name} ends on {end_label} ({days_left} {day_word} remaining).

Upgrade before the trial ends to avoid interruption:

{upgrade_url}

You can choose your plan on the billing page. All prices are shown ex VAT.

— {brand} · {domain}
"""
    return subject, body


def _pick_reminder_key(days_left: int | None) -> str | None:
    if days_left is None:
        return None
    if days_left <= 0:
        return "expired"
    if days_left == 1:
        return "1_day"
    if days_left <= 3:
        return "3_day"
    if days_left <= 7:
        return "7_day"
    return None


def process_trial_reminders(*, conn: Any, as_of: datetime | None = None) -> dict[str, int]:
    """Queue upgrade reminder emails and mark expired trials. Run from cron."""
    now = as_of or _utcnow()
    summary = {"checked": 0, "reminders_sent": 0, "expired": 0}

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, billing_email, trial_ends_at, subscription_status
            FROM tenants
            WHERE subscription_status IN ('trialing', 'provisioning', 'trial_expired')
               OR (trial_ends_at IS NOT NULL AND subscription_status NOT IN ('active', 'cancelled'))
            """
        )
        rows = cur.fetchall()

    for tenant_id, name, billing_email, trial_ends_at, status in rows:
        summary["checked"] += 1
        if not billing_email:
            continue

        days_left = days_until_trial_end(trial_ends_at=trial_ends_at, as_of=now)
        reminder_key = _pick_reminder_key(days_left)
        if not reminder_key:
            continue

        with conn.cursor() as cur:
            if _reminder_already_sent(cur, tenant_id, reminder_key):
                continue

            if reminder_key == "expired" and status != "trial_expired":
                cur.execute(
                    "UPDATE tenants SET subscription_status = 'trial_expired' WHERE id = %s",
                    (tenant_id,),
                )
                summary["expired"] += 1

            subject, body = _email_body(
                tenant_name=name or f"Tenant {tenant_id}",
                days_left=days_left,
                trial_ends_at=trial_ends_at,
                reminder_key=reminder_key,
            )
            _queue_trial_email(
                cur,
                tenant_id=tenant_id,
                to_email=billing_email,
                subject=subject,
                body=body,
                reminder_key=reminder_key,
            )
            summary["reminders_sent"] += 1

    conn.commit()
    return summary


def assert_tenant_access(*, tenant_id: int, conn: Any, master_tenant_id: str) -> None:
    """Deprecated alias — use license_service.assert_tenant_access."""
    from license_service import assert_tenant_access as _assert

    _assert(tenant_id=tenant_id, conn=conn, master_tenant_id=master_tenant_id)


def create_upgrade_checkout(
    *,
    conn: Any,
    tenant_id: int,
    success_url: str | None = None,
    cancel_url: str | None = None,
) -> dict[str, Any]:
    snap = trial_snapshot(tenant_id=tenant_id, conn=conn)
    plan = get_plan(snap["subscription_plan"] or "")
    if not plan:
        plan = get_plan("site_medium_monthly")

    success = success_url or os.getenv(
        "BILLING_UPGRADE_SUCCESS_URL",
        f"{_app_url()}/admin.html?upgraded=1#payroll",
    )
    cancel = cancel_url or os.getenv(
        "BILLING_UPGRADE_CANCEL_URL",
        f"{_app_url()}/admin.html#overview",
    )

    cfg = stripe_settings()
    if not cfg["secret_key"] or not plan:
        return {
            "checkout_url": None,
            "message": "Stripe is not configured. Email support@shiftswifthr.co.uk to upgrade.",
            "upgrade_required": snap["upgrade_required"],
            "trial": snap,
        }

    price_id = resolve_stripe_price_id(plan)
    if not price_id:
        return {
            "checkout_url": None,
            "message": f"Plan price not configured ({plan.stripe_price_id_env}).",
            "upgrade_required": snap["upgrade_required"],
            "trial": snap,
        }

    import stripe

    stripe.api_key = cfg["secret_key"]

    line_items: list[dict[str, object]] = [{"price": price_id, "quantity": 1}]
    payroll_plan = get_payroll_plan(snap["payroll_plan_id"]) if snap["payroll_plan_id"] else None
    if payroll_plan:
        payroll_price_id = resolve_payroll_stripe_price_id(payroll_plan)
        if payroll_price_id:
            line_items.append({"price": payroll_price_id, "quantity": 1})

    session = create_subscription_checkout_session(
        tenant_id=tenant_id,
        line_items=line_items,
        success_url=success,
        cancel_url=cancel,
        metadata={
            "tenant_id": str(tenant_id),
            "plan_id": plan.id,
            "payroll_plan_id": payroll_plan.id if payroll_plan else "",
            "upgrade_after_trial": "1",
        },
        customer_id=snap["stripe_customer_id"],
        customer_email=snap["billing_email"] if not snap["stripe_customer_id"] else None,
    )

    return {
        "checkout_url": session.url,
        "session_id": session.id,
        "upgrade_required": snap["upgrade_required"],
        "trial": snap,
    }
