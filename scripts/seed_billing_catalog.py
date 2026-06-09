#!/usr/bin/env python3
"""Seed editable subscription plans, discount codes, and referral codes."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend_stub"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend_stub" / ".env")
load_dotenv(ROOT / ".env")

import psycopg2

from billing_config import PLANS
from payroll_config import PAYROLL_PLANS

DATABASE_URL = os.getenv("DATABASE_URL")

PLANS_SEED = [
    {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "billing_interval": plan.billing_interval,
        "max_employees": plan.max_employees,
        "price_gbp_ex_vat": plan.price_gbp_ex_vat,
        "features": list(plan.features),
        "stripe_price_id_env": plan.stripe_price_id_env,
        "sort_order": idx,
    }
    for idx, plan in enumerate(PLANS)
]

PAYROLL_PLANS_SEED = [
    {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "billing_interval": plan.billing_interval,
        "max_employees": plan.max_employees,
        "price_gbp_ex_vat": plan.price_gbp_ex_vat,
        "features": list(plan.features),
        "stripe_price_id_env": plan.stripe_price_id_env,
        "sort_order": idx,
    }
    for idx, plan in enumerate(PAYROLL_PLANS)
]

DISCOUNT_CODES = [
    ("LAUNCH20", "Launch offer — 20% off first year", "percent", 20, None, None),
    ("CAFE10", "Café & coffee shop discount", "percent", 10, None, ["site_starter_monthly"]),
    ("WELCOME5", "£5 off monthly plans", "fixed_gbp", 5, None, None),
]

REFERRAL_CODES = [
    ("REF-PUB", "UK Pub Association", "percent", 15, 10, None),
    ("REF-HOSP", "Hospitality partner", "percent", 10, 15, None),
    ("REF-TRIAL", "Extra trial via partner", "trial_days", 14, 5, None),
]


def main() -> None:
    if not DATABASE_URL:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            for item in PLANS_SEED:
                cur.execute(
                    """
                    INSERT INTO subscription_plans (
                      id, name, description, billing_interval, max_employees,
                      price_gbp_ex_vat, features, stripe_price_id_env, sort_order
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      name = EXCLUDED.name,
                      description = EXCLUDED.description,
                      billing_interval = EXCLUDED.billing_interval,
                      max_employees = EXCLUDED.max_employees,
                      price_gbp_ex_vat = EXCLUDED.price_gbp_ex_vat,
                      features = EXCLUDED.features,
                      stripe_price_id_env = EXCLUDED.stripe_price_id_env,
                      sort_order = EXCLUDED.sort_order,
                      updated_at = NOW()
                    """,
                    (
                        item["id"],
                        item["name"],
                        item["description"],
                        item["billing_interval"],
                        item["max_employees"],
                        item["price_gbp_ex_vat"],
                        json.dumps(item["features"]),
                        item["stripe_price_id_env"],
                        item["sort_order"],
                    ),
                )

            for item in PAYROLL_PLANS_SEED:
                cur.execute(
                    """
                    INSERT INTO payroll_plans (
                      id, name, description, billing_interval, max_employees,
                      price_gbp_ex_vat, features, stripe_price_id_env, sort_order
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      name = EXCLUDED.name,
                      description = EXCLUDED.description,
                      billing_interval = EXCLUDED.billing_interval,
                      max_employees = EXCLUDED.max_employees,
                      price_gbp_ex_vat = EXCLUDED.price_gbp_ex_vat,
                      features = EXCLUDED.features,
                      stripe_price_id_env = EXCLUDED.stripe_price_id_env,
                      sort_order = EXCLUDED.sort_order,
                      updated_at = NOW()
                    """,
                    (
                        item["id"],
                        item["name"],
                        item["description"],
                        item["billing_interval"],
                        item["max_employees"],
                        item["price_gbp_ex_vat"],
                        json.dumps(item["features"]),
                        item["stripe_price_id_env"],
                        item["sort_order"],
                    ),
                )

            for code, label, dtype, dvalue, max_redemptions, plans in DISCOUNT_CODES:
                cur.execute(
                    """
                    INSERT INTO discount_codes (code, label, discount_type, discount_value, max_redemptions, applicable_plan_ids)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (code) DO UPDATE SET
                      label = EXCLUDED.label,
                      discount_type = EXCLUDED.discount_type,
                      discount_value = EXCLUDED.discount_value,
                      max_redemptions = EXCLUDED.max_redemptions,
                      applicable_plan_ids = EXCLUDED.applicable_plan_ids,
                      is_active = TRUE
                    """,
                    (code, label, dtype, dvalue, max_redemptions, plans),
                )

            for code, partner, rtype, rvalue, commission, max_uses in REFERRAL_CODES:
                cur.execute(
                    """
                    INSERT INTO referral_codes (code, partner_name, reward_type, reward_value, referrer_commission_percent, max_uses)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (code) DO UPDATE SET
                      partner_name = EXCLUDED.partner_name,
                      reward_type = EXCLUDED.reward_type,
                      reward_value = EXCLUDED.reward_value,
                      referrer_commission_percent = EXCLUDED.referrer_commission_percent,
                      max_uses = EXCLUDED.max_uses,
                      is_active = TRUE
                    """,
                    (code, partner, rtype, rvalue, commission, max_uses),
                )
        conn.commit()
    finally:
        conn.close()

    print("Seeded subscription_plans, payroll_plans, discount_codes, referral_codes.")
    print("Edit platform: UPDATE subscription_plans SET price_gbp_ex_vat = 18.95 WHERE id = 'site_starter_monthly';")
    print("Edit payroll: UPDATE payroll_plans SET price_gbp_ex_vat = 24.95 WHERE id = 'payroll_starter_monthly';")


if __name__ == "__main__":
    main()
