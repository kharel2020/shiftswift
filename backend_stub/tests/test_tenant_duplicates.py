"""Duplicate tenant detection — one billing email, one authentic workspace."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from modules.master.service import annotate_duplicate_billing_emails, _pick_canonical_tenant_id


def test_pick_canonical_prefers_matching_hr_login() -> None:
    tenants = [
        {
            "id": 10,
            "billing_email": "hr@acme.co.uk",
            "hr_login_email": None,
            "created_at": "2026-06-01",
        },
        {
            "id": 11,
            "billing_email": "hr@acme.co.uk",
            "hr_login_email": "hr@acme.co.uk",
            "created_at": "2026-06-02",
        },
    ]
    assert _pick_canonical_tenant_id(tenants) == 11


def test_annotate_duplicate_billing_emails() -> None:
    tenants = [
        {
            "id": 1,
            "billing_email": "a@test.co.uk",
            "hr_login_email": "a@test.co.uk",
            "created_at": "2026-06-01",
        },
        {
            "id": 2,
            "billing_email": "a@test.co.uk",
            "hr_login_email": None,
            "created_at": "2026-06-02",
        },
        {
            "id": 3,
            "billing_email": "b@test.co.uk",
            "hr_login_email": "b@test.co.uk",
            "created_at": "2026-06-01",
        },
    ]
    annotate_duplicate_billing_emails(tenants)
    by_id = {row["id"]: row for row in tenants}
    assert by_id[1]["is_canonical_tenant"] is True
    assert by_id[2]["is_canonical_tenant"] is False
    assert by_id[3]["duplicate_billing_email"] is False
