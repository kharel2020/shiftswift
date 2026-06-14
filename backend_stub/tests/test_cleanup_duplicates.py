"""Duplicate tenant cleanup — preview vs confirm."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from modules.master.platform_ops import _duplicate_billing_groups, cleanup_duplicate_tenants
from modules.master.service import _pick_canonical_tenant_id


def _tenant(
    tenant_id: int,
    *,
    email: str,
    name: str,
    created_at: str,
    hr_login_email: str | None = None,
) -> dict:
    return {
        "id": tenant_id,
        "billing_email": email,
        "name": name,
        "created_at": created_at,
        "hr_login_email": hr_login_email,
        "duplicate_billing_email": True,
        "is_canonical_tenant": False,
    }


def test_duplicate_billing_groups_only_multi_email() -> None:
    rows = [
        _tenant(1, email="a@x.com", name="A1", created_at="2026-01-01T00:00:00+00:00"),
        _tenant(2, email="a@x.com", name="A2", created_at="2026-01-02T00:00:00+00:00"),
        _tenant(3, email="solo@x.com", name="Solo", created_at="2026-01-01T00:00:00+00:00"),
    ]
    groups = _duplicate_billing_groups(rows)
    assert list(groups.keys()) == ["a@x.com"]
    assert len(groups["a@x.com"]) == 2


def test_pick_canonical_prefers_newest_when_no_hr_login() -> None:
    rows = [
        _tenant(10, email="a@x.com", name="Old", created_at="2026-01-01T00:00:00+00:00"),
        _tenant(11, email="a@x.com", name="New", created_at="2026-06-01T00:00:00+00:00"),
    ]
    assert _pick_canonical_tenant_id(rows) == 11


def test_cleanup_duplicate_tenants_dry_run_marks_would_delete() -> None:
    conn = MagicMock()
    tenants = [
        _tenant(10, email="dup@x.com", name="Keep", created_at="2026-06-01T00:00:00+00:00"),
        _tenant(11, email="dup@x.com", name="Remove", created_at="2026-01-01T00:00:00+00:00"),
    ]

    import modules.master.platform_ops as ops

    original = ops.list_tenants
    ops.list_tenants = lambda **kwargs: tenants
    try:
        result = cleanup_duplicate_tenants(
            conn=conn,
            master_tenant_id=999,
            master_username="admin@test",
            dry_run=True,
        )
    finally:
        ops.list_tenants = original

    assert result["dry_run"] is True
    assert result["deleted_count"] == 0
    assert len(result["removed"]) == 1
    assert result["removed"][0]["tenant_id"] == 11
    assert result["removed"][0]["action"] == "would_soft_delete"
    conn.cursor.assert_not_called()
