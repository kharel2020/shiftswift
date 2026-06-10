"""Introducer commission CSV export tests."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from partner_commission_service import build_introducer_commission_csv, introducer_export_filename


def test_build_introducer_commission_csv_header() -> None:
    csv_body = build_introducer_commission_csv([])
    lines = csv_body.strip().splitlines()
    assert lines[0].startswith("tenant_id,business_name,billing_email")
    assert "estimated_commission_ex_vat" in lines[0]


def test_introducer_export_filename_sanitizes_code() -> None:
    name = introducer_export_filename(referral_code="REF/SMITH HR")
    assert "REF-SMITH-HR" in name
    assert name.endswith(".csv")


def test_fetch_introducer_commission_rows_empty() -> None:
    from partner_commission_service import fetch_introducer_commission_rows

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = []
    rows = fetch_introducer_commission_rows(conn=conn)
    assert rows == []
