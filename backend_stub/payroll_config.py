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


# Payroll add-on bands — strategy doc (billed separately from HR platform).
PAYROLL_PLANS: tuple[PayrollPlan, ...] = (
    PayrollPlan(
        id="payroll_starter_monthly",
        name="1–10 employees",
        description="Pay cycles, payslips, HMRC RTI, P60/P45 generation.",
        stripe_price_id_env="STRIPE_PRICE_PAYROLL_STARTER_MONTHLY",
        billing_interval="month",
        max_employees=10,
        price_gbp_ex_vat=19.0,
        features=("HMRC RTI submissions", "Payslips & P60s", "P45 generation"),
    ),
    PayrollPlan(
        id="payroll_standard_monthly",
        name="11–25 employees",
        description="All Starter features plus auto-enrolment pension reporting.",
        stripe_price_id_env="STRIPE_PRICE_PAYROLL_STANDARD_MONTHLY",
        billing_interval="month",
        max_employees=25,
        price_gbp_ex_vat=35.0,
        features=("Everything in 1–10 band", "Auto-enrolment pension reporting"),
    ),
    PayrollPlan(
        id="payroll_growth_monthly",
        name="26–50 employees",
        description="All Standard features plus multi-site payroll runs.",
        stripe_price_id_env="STRIPE_PRICE_PAYROLL_GROWTH_MONTHLY",
        billing_interval="month",
        max_employees=50,
        price_gbp_ex_vat=55.0,
        features=("Everything in 11–25 band", "Multi-site payroll runs"),
    ),
    PayrollPlan(
        id="payroll_scale_monthly",
        name="51–100 employees",
        description="All Growth features plus dedicated payroll support line.",
        stripe_price_id_env="STRIPE_PRICE_PAYROLL_SCALE_MONTHLY",
        billing_interval="month",
        max_employees=100,
        price_gbp_ex_vat=85.0,
        features=("Everything in 26–50 band", "Dedicated payroll support line"),
    ),
)


def get_payroll_plan(plan_id: str) -> PayrollPlan | None:
    return next((plan for plan in PAYROLL_PLANS if plan.id == plan_id), None)
