"""Stripe checkout / Direct Debit configuration tests."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from billing_config import stripe_payment_method_types, stripe_settings  # noqa: E402


def test_default_payment_methods_include_bacs() -> None:
    methods = stripe_payment_method_types()
    assert "bacs_debit" in methods
    assert "card" in methods


def test_stripe_settings_direct_debit_flag() -> None:
    settings = stripe_settings()
    assert settings["direct_debit_enabled"] is True
