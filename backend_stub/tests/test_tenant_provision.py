"""Manual tenant provisioning helpers."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from modules.master.tenant_provision import generate_temporary_password, list_provision_plans


def test_generate_temporary_password_length() -> None:
    password = generate_temporary_password()
    assert password.startswith("Shift-")
    assert len(password) >= 12


def test_list_provision_plans_has_defaults() -> None:
    plans = list_provision_plans()
    assert plans
    ids = {plan["id"] for plan in plans}
    assert "site_medium_monthly" in ids
