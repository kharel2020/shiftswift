"""Notification recipient routing."""

from __future__ import annotations

from core.notifications import fetch_tenant_contacts, resolve_email_recipient


def test_resolve_billing_prefers_billing_email() -> None:
    contacts = {
        "billing_email": "billing@example.com",
        "signatory_email": "sign@example.com",
        "hr_email": "hr@example.com",
        "tenant_name": "Acme",
    }
    assert resolve_email_recipient(purpose="billing", contacts=contacts) == "billing@example.com"


def test_resolve_contract_prefers_signatory() -> None:
    contacts = {
        "billing_email": "billing@example.com",
        "signatory_email": "sign@example.com",
        "hr_email": None,
        "tenant_name": "Acme",
    }
    assert resolve_email_recipient(purpose="contract", contacts=contacts) == "sign@example.com"


def test_resolve_contract_falls_back_to_billing() -> None:
    contacts = {
        "billing_email": "billing@example.com",
        "signatory_email": None,
        "hr_email": None,
        "tenant_name": "Acme",
    }
    assert resolve_email_recipient(purpose="contract", contacts=contacts) == "billing@example.com"


def test_resolve_compliance_prefers_billing_then_hr() -> None:
    contacts = {
        "billing_email": None,
        "signatory_email": "sign@example.com",
        "hr_email": "hr@example.com",
        "tenant_name": "Acme",
    }
    assert resolve_email_recipient(purpose="compliance", contacts=contacts) == "hr@example.com"


def test_explicit_to_overrides_contacts() -> None:
    contacts = {"billing_email": "billing@example.com", "signatory_email": None, "hr_email": None, "tenant_name": "X"}
    assert (
        resolve_email_recipient(purpose="compliance", contacts=contacts, explicit="override@example.com")
        == "override@example.com"
    )
