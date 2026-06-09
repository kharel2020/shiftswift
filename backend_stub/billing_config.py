"""Stripe Billing configuration and B2B subscription tiers."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SubscriptionPlan:
    id: str
    name: str
    description: str
    stripe_price_id_env: str
    billing_interval: str
    max_employees: int
    price_gbp_ex_vat: float
    features: tuple[str, ...]


# Flat per-site pricing with employee bands (UK restaurants, cafés, pubs).
# Create matching Products/Prices in Stripe Dashboard, then set env vars below.
PLANS: tuple[SubscriptionPlan, ...] = (
    SubscriptionPlan(
        id="site_starter_monthly",
        name="Starter",
        description="Up to 10 employees at one restaurant, café, or pub.",
        stripe_price_id_env="STRIPE_PRICE_SITE_STARTER_MONTHLY",
        billing_interval="month",
        max_employees=10,
        price_gbp_ex_vat=18.95,
        features=("Core HR", "Rota basics", "Sponsor compliance module"),
    ),
    SubscriptionPlan(
        id="site_medium_monthly",
        name="Medium",
        description="Up to 25 employees at one site.",
        stripe_price_id_env="STRIPE_PRICE_SITE_MEDIUM_MONTHLY",
        billing_interval="month",
        max_employees=25,
        price_gbp_ex_vat=49.0,
        features=("Everything in Starter", "Advanced rota rules", "Extended compliance"),
    ),
    SubscriptionPlan(
        id="site_growth_monthly",
        name="Growth",
        description="Up to 50 employees at one site.",
        stripe_price_id_env="STRIPE_PRICE_SITE_GROWTH_MONTHLY",
        billing_interval="month",
        max_employees=50,
        price_gbp_ex_vat=79.0,
        features=("Everything in Medium", "Priority support", "Multi-role RBAC"),
    ),
    SubscriptionPlan(
        id="site_starter_annual",
        name="Starter — annual",
        description="Up to 10 employees, billed annually (2 months free vs monthly).",
        stripe_price_id_env="STRIPE_PRICE_SITE_STARTER_ANNUAL",
        billing_interval="year",
        max_employees=10,
        price_gbp_ex_vat=189.50,
        features=("Core HR", "Rota basics", "Sponsor compliance module"),
    ),
)


def get_plan(plan_id: str) -> SubscriptionPlan | None:
    return next((plan for plan in PLANS if plan.id == plan_id), None)


def stripe_payment_method_types() -> list[str]:
    """UK B2B default: Bacs Direct Debit + card backup."""
    raw = os.getenv("STRIPE_PAYMENT_METHODS", "bacs_debit,card")
    methods = [part.strip() for part in raw.split(",") if part.strip()]
    return methods or ["bacs_debit", "card"]


def stripe_settings() -> dict[str, str | bool]:
    return {
        "secret_key": os.getenv("STRIPE_SECRET_KEY", ""),
        "webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET", ""),
        "tax_enabled": os.getenv("STRIPE_TAX_ENABLED", "1").lower() in {"1", "true", "yes"},
        "currency": os.getenv("STRIPE_CURRENCY", "gbp"),
        "configured": bool(os.getenv("STRIPE_SECRET_KEY")),
        "direct_debit_enabled": "bacs_debit" in stripe_payment_method_types(),
    }


def plan_catalog() -> list[dict[str, object]]:
    settings = stripe_settings()
    items: list[dict[str, object]] = []
    for plan in PLANS:
        price_id = os.getenv(plan.stripe_price_id_env, "")
        items.append(
            {
                "id": plan.id,
                "name": plan.name,
                "description": plan.description,
                "billing_interval": plan.billing_interval,
                "max_employees": plan.max_employees,
                "price_gbp_ex_vat": plan.price_gbp_ex_vat,
                "price_gbp_inc_vat": round(plan.price_gbp_ex_vat * 1.2, 2),
                "vat_rate": "20%",
                "features": list(plan.features),
                "stripe_price_configured": bool(price_id),
            }
        )
    items.append(
        {
            "billing_model": "flat_per_site",
            "note": "UK B2B SaaS — VAT at 20% added at checkout via Stripe Tax when enabled.",
            "stripe_configured": settings["configured"],
            "stripe_tax_enabled": settings["tax_enabled"],
        }
    )
    return items
