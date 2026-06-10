"""Per-head billing quote tests."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from billing_config import get_plan
from billing_pricing import calculate_monthly_quote, plan_pricing_payload


def test_essentials_quote_at_ten_staff() -> None:
    plan = get_plan("site_starter_monthly")
    assert plan is not None
    quote = calculate_monthly_quote(plan, active_employees=10)
    assert quote["base_gbp_ex_vat"] == 9.0
    assert quote["variable_gbp_ex_vat"] == 20.0
    assert quote["total_gbp_ex_vat"] == 29.0
    assert quote["cap_applied"] is False


def test_compliance_quote_hits_cap() -> None:
    plan = get_plan("site_medium_monthly")
    assert plan is not None
    quote = calculate_monthly_quote(plan, active_employees=30)
    assert quote["subtotal_gbp_ex_vat"] == 109.0
    assert quote["total_gbp_ex_vat"] == 79.0
    assert quote["cap_applied"] is True


def test_plan_pricing_payload_includes_examples() -> None:
    plan = get_plan("site_medium_monthly")
    assert plan is not None
    payload = plan_pricing_payload(plan)
    assert payload["billing_model"] == "base_plus_per_head"
    assert len(payload["example_quotes"]) >= 2
