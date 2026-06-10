"""Stripe seat sync helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from billing_config import get_plan
from billing_seat_sync import build_platform_subscription_items, count_active_employees


def test_count_active_employees() -> None:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.return_value = (12,)

    assert count_active_employees(tenant_id=7, conn=conn) == 12
    cursor.execute.assert_called_once()


def test_build_platform_subscription_items_with_seats() -> None:
    plan = get_plan("site_medium_monthly")
    assert plan is not None
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.return_value = (10,)

    with patch("billing_seat_sync.resolve_stripe_price_id", return_value="price_base"), patch(
        "billing_seat_sync.resolve_stripe_seat_price_id", return_value="price_seat"
    ):
        items = build_platform_subscription_items(plan=plan, conn=conn, tenant_id=1)

    assert items == [
        {"price": "price_base", "quantity": 1},
        {"price": "price_seat", "quantity": 10},
    ]
