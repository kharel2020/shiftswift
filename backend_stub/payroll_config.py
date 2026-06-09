"""Payroll add-on pricing — separate from platform HR subscription tiers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PayrollPlan:
    id: str
    name: str
    description: str
    stripe_price_id_env: str
    billing_interval: str
    max_employees: int
    price_gbp_ex_vat: float
    features: tuple[str, ...]


# Flat per-site payroll add-on with employee bands (matches platform tiers).
# HMRC RTI, payslips, and statutory reporting — billed as a second Stripe subscription item.
PAYROLL_PLANS: tuple[PayrollPlan, ...] = (
    PayrollPlan(
        id="payroll_starter_monthly",
        name="Payroll — Starter",
        description="Full UK payroll for up to 10 employees at one site.",
        stripe_price_id_env="STRIPE_PRICE_PAYROLL_STARTER_MONTHLY",
        billing_interval="month",
        max_employees=10,
        price_gbp_ex_vat=24.95,
        features=("HMRC RTI submissions", "Payslips & P60s", "Pension auto-enrolment export"),
    ),
    PayrollPlan(
        id="payroll_standard_monthly",
        name="Payroll — Standard",
        description="Full UK payroll for up to 25 employees at one site.",
        stripe_price_id_env="STRIPE_PRICE_PAYROLL_STANDARD_MONTHLY",
        billing_interval="month",
        max_employees=25,
        price_gbp_ex_vat=49.0,
        features=("Everything in Payroll Starter", "Multi-rate pay rules", "Tips & tronc allocation export"),
    ),
    PayrollPlan(
        id="payroll_growth_monthly",
        name="Payroll — Growth",
        description="Full UK payroll for up to 50 employees at one site.",
        stripe_price_id_env="STRIPE_PRICE_PAYROLL_GROWTH_MONTHLY",
        billing_interval="month",
        max_employees=50,
        price_gbp_ex_vat=69.0,
        features=("Everything in Payroll Standard", "Priority payroll support", "Year-end filing pack"),
    ),
)


def get_payroll_plan(plan_id: str) -> PayrollPlan | None:
    return next((plan for plan in PAYROLL_PLANS if plan.id == plan_id), None)
