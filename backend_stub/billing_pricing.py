"""Per-head subscription quotes — base + active employees, with monthly cap."""

from __future__ import annotations

from typing import Any, Protocol


class PlanPricing(Protocol):
    base_price_gbp_ex_vat: float
    price_per_active_employee_gbp_ex_vat: float
    monthly_cap_gbp_ex_vat: float | None
    price_gbp_ex_vat: float
    max_employees: int


def plan_base_price(plan: PlanPricing) -> float:
    base = getattr(plan, "base_price_gbp_ex_vat", None)
    if base is not None and float(base) > 0:
        return float(base)
    return float(plan.price_gbp_ex_vat)


def plan_per_head_price(plan: PlanPricing) -> float:
    return float(getattr(plan, "price_per_active_employee_gbp_ex_vat", 0) or 0)


def plan_monthly_cap(plan: PlanPricing) -> float | None:
    cap = getattr(plan, "monthly_cap_gbp_ex_vat", None)
    if cap is None:
        return None
    value = float(cap)
    return value if value > 0 else None


def calculate_monthly_quote(
    plan: PlanPricing,
    *,
    active_employees: int,
) -> dict[str, Any]:
    """Return ex-VAT monthly bill for a plan and active headcount."""
    seats = max(0, int(active_employees))
    base = plan_base_price(plan)
    per_head = plan_per_head_price(plan)
    variable = round(seats * per_head, 2)
    subtotal = round(base + variable, 2)
    cap = plan_monthly_cap(plan)
    capped = round(min(subtotal, cap), 2) if cap is not None else subtotal
    return {
        "active_employees": seats,
        "base_gbp_ex_vat": base,
        "per_head_gbp_ex_vat": per_head,
        "variable_gbp_ex_vat": variable,
        "subtotal_gbp_ex_vat": subtotal,
        "monthly_cap_gbp_ex_vat": cap,
        "total_gbp_ex_vat": capped,
        "total_gbp_inc_vat": round(capped * 1.2, 2),
        "cap_applied": cap is not None and subtotal > cap,
    }


def example_headcounts(plan: PlanPricing) -> list[int]:
    """Headcounts for marketing examples (5, 10, 20) within plan max."""
    cap = plan.max_employees
    samples = [5, 10, 20]
    return [n for n in samples if n <= cap] or [min(5, cap)]


def plan_pricing_payload(plan: PlanPricing) -> dict[str, Any]:
    base = plan_base_price(plan)
    per_head = plan_per_head_price(plan)
    cap = plan_monthly_cap(plan)
    examples = [
        {"active_employees": n, **calculate_monthly_quote(plan, active_employees=n)}
        for n in example_headcounts(plan)
    ]
    return {
        "billing_model": "base_plus_per_head" if per_head > 0 else "flat",
        "base_price_gbp_ex_vat": base,
        "price_per_active_employee_gbp_ex_vat": per_head,
        "monthly_cap_gbp_ex_vat": cap,
        "from_price_gbp_ex_vat": base,
        "example_quotes": examples,
    }
