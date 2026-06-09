"""Stripe Checkout helpers — UK Bacs Direct Debit mandates and subscriptions."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from billing_config import stripe_payment_method_types, stripe_settings


def _configure_stripe() -> Any:
    import stripe

    cfg = stripe_settings()
    if not cfg["secret_key"]:
        raise RuntimeError("Stripe not configured")
    stripe.api_key = cfg["secret_key"]
    return stripe


def _app_success_url(default: str) -> str:
    return os.getenv("BILLING_MANDATE_SUCCESS_URL", default)


def _app_cancel_url(default: str) -> str:
    return os.getenv("BILLING_MANDATE_CANCEL_URL", default)


def mandate_metadata(*, tenant_id: int, purpose: str) -> dict[str, str]:
    return {
        "tenant_id": str(tenant_id),
        "purpose": purpose,
        "platform": "hr",
    }


def create_subscription_checkout_session(
    *,
    tenant_id: int,
    line_items: list[dict[str, object]],
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str],
    customer_id: str | None = None,
    customer_email: str | None = None,
) -> Any:
    """Stripe Checkout for subscription — card + Bacs Direct Debit (UK)."""
    stripe = _configure_stripe()
    cfg = stripe_settings()

    session_kwargs: dict[str, object] = {
        "mode": "subscription",
        "payment_method_types": stripe_payment_method_types(),
        "line_items": line_items,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(tenant_id),
        "metadata": metadata,
        "automatic_tax": {"enabled": bool(cfg["tax_enabled"])},
        "tax_id_collection": {"enabled": True},
        "payment_method_collection": "always",
    }

    if customer_id:
        session_kwargs["customer"] = customer_id
    elif customer_email:
        session_kwargs["customer_email"] = customer_email

    return stripe.checkout.Session.create(**session_kwargs)


def create_direct_debit_mandate_session(
    *,
    tenant_id: int,
    customer_id: str,
    success_url: str | None = None,
    cancel_url: str | None = None,
    purpose: str = "subscription_billing",
) -> Any:
    """Collect a UK Bacs Direct Debit mandate via Stripe Checkout (setup mode)."""
    stripe = _configure_stripe()
    success = success_url or _app_success_url(
        f"{os.getenv('LOCAL_APP_URL', 'http://localhost:5173')}/admin.html?mandate=confirmed#payroll"
    )
    cancel = cancel_url or _app_cancel_url(
        f"{os.getenv('LOCAL_APP_URL', 'http://localhost:5173')}/admin.html?mandate=cancelled#payroll"
    )

    return stripe.checkout.Session.create(
        mode="setup",
        customer=customer_id,
        payment_method_types=["bacs_debit"],
        success_url=success,
        cancel_url=cancel,
        metadata=mandate_metadata(tenant_id=tenant_id, purpose=purpose),
    )


def extract_mandate_from_payment_method(stripe: Any, payment_method_id: str) -> dict[str, Any]:
    pm = stripe.PaymentMethod.retrieve(payment_method_id)
    result: dict[str, Any] = {
        "payment_method_type": pm.type,
        "stripe_payment_method_id": pm.id,
        "stripe_mandate_id": None,
        "mandate_status": "none",
        "mandate_sort_code": None,
        "mandate_account_last4": None,
    }

    if pm.type == "bacs_debit" and pm.bacs_debit:
        result["mandate_sort_code"] = getattr(pm.bacs_debit, "sort_code", None)
        result["mandate_account_last4"] = getattr(pm.bacs_debit, "last4", None)

    mandates = stripe.Mandate.list(payment_method=payment_method_id, limit=1)
    if mandates.data:
        mandate = mandates.data[0]
        result["stripe_mandate_id"] = mandate.id
        result["mandate_status"] = mandate.status or "pending"

    return result


def apply_payment_method_to_billing(
    stripe: Any,
    *,
    customer_id: str,
    payment_method_id: str,
    subscription_id: str | None = None,
) -> None:
    stripe.Customer.modify(
        customer_id,
        invoice_settings={"default_payment_method": payment_method_id},
    )
    if subscription_id:
        stripe.Subscription.modify(
            subscription_id,
            default_payment_method=payment_method_id,
        )


def sync_mandate_from_setup_intent(
    *,
    conn: Any,
    tenant_id: int,
    setup_intent_id: str,
    subscription_id: str | None = None,
) -> dict[str, Any]:
    stripe = _configure_stripe()
    setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
    payment_method_id = setup_intent.payment_method
    if not payment_method_id:
        raise ValueError("SetupIntent has no payment method")

    customer_id = setup_intent.customer
    apply_payment_method_to_billing(
        stripe,
        customer_id=customer_id,
        payment_method_id=payment_method_id,
        subscription_id=subscription_id,
    )

    mandate = extract_mandate_from_payment_method(stripe, payment_method_id)
    confirmed_at = datetime.now(timezone.utc) if mandate["mandate_status"] in {"active", "pending"} else None

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tenants SET
              payment_method_type = %s,
              stripe_payment_method_id = %s,
              stripe_mandate_id = %s,
              mandate_status = %s,
              mandate_sort_code = %s,
              mandate_account_last4 = %s,
              mandate_confirmed_at = COALESCE(%s, mandate_confirmed_at)
            WHERE id = %s
            """,
            (
                mandate["payment_method_type"],
                mandate["stripe_payment_method_id"],
                mandate["stripe_mandate_id"],
                mandate["mandate_status"],
                mandate["mandate_sort_code"],
                mandate["mandate_account_last4"],
                confirmed_at,
                tenant_id,
            ),
        )
    conn.commit()
    return mandate


def sync_mandate_status(
    *,
    conn: Any,
    tenant_id: int,
    mandate_id: str,
    status: str,
) -> None:
    confirmed_at = datetime.now(timezone.utc) if status == "active" else None
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tenants SET
              mandate_status = %s,
              mandate_confirmed_at = CASE WHEN %s = 'active' THEN COALESCE(mandate_confirmed_at, %s) ELSE mandate_confirmed_at END
            WHERE id = %s AND stripe_mandate_id = %s
            """,
            (status, status, confirmed_at, tenant_id, mandate_id),
        )
    conn.commit()


def fetch_tenant_mandate(cur: Any, tenant_id: int) -> dict[str, Any]:
    cur.execute(
        """
        SELECT payment_method_type, stripe_payment_method_id, stripe_mandate_id,
               mandate_status, mandate_sort_code, mandate_account_last4,
               mandate_confirmed_at, stripe_customer_id, stripe_subscription_id, billing_email
        FROM tenants WHERE id = %s
        """,
        (tenant_id,),
    )
    row = cur.fetchone()
    if not row:
        return {"mandate_status": "none"}

    (
        pm_type,
        pm_id,
        mandate_id,
        mandate_status,
        sort_code,
        last4,
        confirmed_at,
        customer_id,
        subscription_id,
        billing_email,
    ) = row

    return {
        "payment_method_type": pm_type,
        "stripe_payment_method_id": pm_id,
        "stripe_mandate_id": mandate_id,
        "mandate_status": mandate_status or "none",
        "mandate_sort_code": sort_code,
        "mandate_account_last4": last4,
        "mandate_confirmed_at": confirmed_at.isoformat() if isinstance(confirmed_at, datetime) else confirmed_at,
        "direct_debit_active": mandate_status == "active",
        "direct_debit_pending": mandate_status == "pending",
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "billing_email": billing_email,
    }


def create_mandate_checkout_for_tenant(
    *,
    conn: Any,
    tenant_id: int,
    success_url: str | None = None,
    cancel_url: str | None = None,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        mandate_info = fetch_tenant_mandate(cur, tenant_id)

    customer_id = mandate_info.get("stripe_customer_id")
    if not customer_id:
        return {
            "checkout_url": None,
            "message": "No Stripe customer yet. Complete signup or upgrade first.",
            "mandate": mandate_info,
        }

    session = create_direct_debit_mandate_session(
        tenant_id=tenant_id,
        customer_id=customer_id,
        success_url=success_url,
        cancel_url=cancel_url,
        purpose="direct_debit_mandate",
    )
    return {
        "checkout_url": session.url,
        "session_id": session.id,
        "mandate": mandate_info,
        "message": "Complete Direct Debit setup on Stripe — UK Bacs mandate for monthly billing.",
    }
