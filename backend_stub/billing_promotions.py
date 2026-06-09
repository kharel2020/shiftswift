"""Discount and referral code validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class PromotionResult:
    valid: bool
    message: str
    discount_code: str | None = None
    referral_code: str | None = None
    discount_type: str | None = None
    discount_value: float = 0.0
    discount_amount_gbp: float = 0.0
    extra_trial_days: int = 0
    stripe_coupon_ids: list[str] | None = None
    partner_name: str | None = None


def _db_conn() -> Any:
    import psycopg2

    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    return psycopg2.connect(url)


def _normalize_code(code: str | None) -> str | None:
    if not code:
        return None
    cleaned = code.strip().upper()
    return cleaned or None


def validate_promotions(
    *,
    plan_id: str,
    base_price_gbp: float,
    discount_code: str | None = None,
    referral_code: str | None = None,
) -> PromotionResult:
    discount_code = _normalize_code(discount_code)
    referral_code = _normalize_code(referral_code)
    if not discount_code and not referral_code:
        return PromotionResult(valid=True, message="No promotion applied")

    conn = _db_conn()
    if not conn:
        return PromotionResult(valid=False, message="Promotions unavailable")

    discount_amount = 0.0
    extra_trial = 0
    stripe_coupons: list[str] = []
    messages: list[str] = []
    partner_name = None

    try:
        with conn.cursor() as cur:
            if discount_code:
                cur.execute(
                    """
                    SELECT code, label, discount_type, discount_value, stripe_coupon_id,
                           valid_from, valid_until, max_redemptions, redemption_count,
                           applicable_plan_ids, is_active
                    FROM discount_codes WHERE upper(code) = upper(%s)
                    """,
                    (discount_code,),
                )
                row = cur.fetchone()
                if not row:
                    return PromotionResult(valid=False, message="Invalid discount code")
                (
                    code,
                    label,
                    dtype,
                    dvalue,
                    stripe_coupon,
                    valid_from,
                    valid_until,
                    max_redemptions,
                    redemption_count,
                    applicable_plans,
                    is_active,
                ) = row
                now = datetime.now(timezone.utc)
                if not is_active:
                    return PromotionResult(valid=False, message="Discount code is not active")
                if valid_from and valid_from > now:
                    return PromotionResult(valid=False, message="Discount code is not yet valid")
                if valid_until and valid_until < now:
                    return PromotionResult(valid=False, message="Discount code has expired")
                if max_redemptions is not None and redemption_count >= max_redemptions:
                    return PromotionResult(valid=False, message="Discount code has reached its limit")
                if applicable_plans and plan_id not in applicable_plans:
                    return PromotionResult(valid=False, message="Discount code does not apply to this plan")

                if dtype == "percent":
                    discount_amount += round(base_price_gbp * float(dvalue) / 100, 2)
                else:
                    discount_amount += float(dvalue)
                if stripe_coupon:
                    stripe_coupons.append(stripe_coupon)
                messages.append(label or f"{code} discount applied")

            if referral_code:
                cur.execute(
                    """
                    SELECT code, partner_name, reward_type, reward_value, stripe_coupon_id,
                           max_uses, use_count, is_active
                    FROM referral_codes WHERE upper(code) = upper(%s)
                    """,
                    (referral_code,),
                )
                row = cur.fetchone()
                if not row:
                    return PromotionResult(valid=False, message="Invalid referral code")
                (
                    code,
                    partner_name,
                    rtype,
                    rvalue,
                    stripe_coupon,
                    max_uses,
                    use_count,
                    is_active,
                ) = row
                if not is_active:
                    return PromotionResult(valid=False, message="Referral code is not active")
                if max_uses is not None and use_count >= max_uses:
                    return PromotionResult(valid=False, message="Referral code has reached its limit")

                if rtype == "percent":
                    discount_amount += round(base_price_gbp * float(rvalue) / 100, 2)
                elif rtype == "fixed_gbp":
                    discount_amount += float(rvalue)
                elif rtype == "trial_days":
                    extra_trial += int(rvalue)
                if stripe_coupon:
                    stripe_coupons.append(stripe_coupon)
                messages.append(f"Referral from {partner_name}")

        discount_amount = min(discount_amount, base_price_gbp)
        return PromotionResult(
            valid=True,
            message=" · ".join(messages) if messages else "Promotion applied",
            discount_code=discount_code,
            referral_code=referral_code,
            discount_amount_gbp=round(discount_amount, 2),
            extra_trial_days=extra_trial,
            stripe_coupon_ids=stripe_coupons or None,
            partner_name=partner_name,
        )
    finally:
        conn.close()


def record_promotion_redemption(
    *,
    tenant_id: int,
    plan_id: str,
    promotion: PromotionResult,
    conn: Any,
) -> None:
    with conn.cursor() as cur:
        if promotion.discount_code:
            cur.execute(
                """
                UPDATE discount_codes
                SET redemption_count = redemption_count + 1
                WHERE upper(code) = upper(%s)
                """,
                (promotion.discount_code,),
            )
        if promotion.referral_code:
            cur.execute(
                """
                UPDATE referral_codes
                SET use_count = use_count + 1
                WHERE upper(code) = upper(%s)
                """,
                (promotion.referral_code,),
            )
        cur.execute(
            """
            INSERT INTO promotion_redemptions
              (tenant_id, discount_code, referral_code, plan_id, discount_applied_gbp, extra_trial_days)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_id,
                promotion.discount_code,
                promotion.referral_code,
                plan_id,
                promotion.discount_amount_gbp,
                promotion.extra_trial_days,
            ),
        )


def list_discount_codes(*, conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT code, label, discount_type, discount_value, valid_from, valid_until,
                   max_redemptions, redemption_count, applicable_plan_ids, is_active
            FROM discount_codes
            ORDER BY code
            """
        )
        items: list[dict[str, Any]] = []
        for row in cur.fetchall():
            items.append(
                {
                    "code": row[0],
                    "label": row[1],
                    "discount_type": row[2],
                    "discount_value": float(row[3]),
                    "valid_from": row[4].isoformat() if row[4] else None,
                    "valid_until": row[5].isoformat() if row[5] else None,
                    "max_redemptions": row[6],
                    "redemption_count": row[7],
                    "applicable_plan_ids": list(row[8] or []),
                    "is_active": row[9],
                }
            )
        return items


def list_referral_codes(*, conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT code, partner_name, reward_type, reward_value, referrer_commission_percent,
                   max_uses, use_count, is_active
            FROM referral_codes
            ORDER BY code
            """
        )
        items: list[dict[str, Any]] = []
        for row in cur.fetchall():
            items.append(
                {
                    "code": row[0],
                    "partner_name": row[1],
                    "reward_type": row[2],
                    "reward_value": float(row[3]),
                    "referrer_commission_percent": float(row[4]),
                    "max_uses": row[5],
                    "use_count": row[6],
                    "is_active": row[7],
                }
            )
        return items
