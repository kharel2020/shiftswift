"""Load payroll add-on plans from database (editable) with code fallback."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from payroll_config import PAYROLL_PLANS as DEFAULT_PAYROLL_PLANS


@dataclass(frozen=True)
class PayrollPlan:
    id: str
    name: str
    description: str
    stripe_price_id_env: str
    billing_interval: str
    max_employees: int
    price_gbp_ex_vat: float
    features: tuple[str, ...]
    stripe_price_id: str | None = None


def _db_conn() -> Any:
    import psycopg2

    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    return psycopg2.connect(url)


def _row_to_plan(row: tuple) -> PayrollPlan:
    plan_id, name, description, interval, max_emp, price, features, env_key, stripe_price = row
    if isinstance(features, str):
        feature_list = json.loads(features)
    else:
        feature_list = features or []
    return PayrollPlan(
        id=plan_id,
        name=name,
        description=description or "",
        stripe_price_id_env=env_key or "",
        billing_interval=interval,
        max_employees=int(max_emp),
        price_gbp_ex_vat=float(price),
        features=tuple(feature_list),
        stripe_price_id=stripe_price,
    )


def list_payroll_plans_from_db(active_only: bool = True) -> list[PayrollPlan]:
    conn = _db_conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT id, name, description, billing_interval, max_employees,
                       price_gbp_ex_vat, features, stripe_price_id_env, stripe_price_id
                FROM payroll_plans
            """
            if active_only:
                sql += " WHERE is_active = TRUE"
            sql += " ORDER BY sort_order ASC, price_gbp_ex_vat ASC"
            cur.execute(sql)
            rows = cur.fetchall()
        return [_row_to_plan(row) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_payroll_plan(plan_id: str) -> PayrollPlan | None:
    conn = _db_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, description, billing_interval, max_employees,
                           price_gbp_ex_vat, features, stripe_price_id_env, stripe_price_id
                    FROM payroll_plans
                    WHERE id = %s AND is_active = TRUE
                    """,
                    (plan_id,),
                )
                row = cur.fetchone()
                if row:
                    return _row_to_plan(row)
        except Exception:
            pass
        finally:
            conn.close()

    for plan in DEFAULT_PAYROLL_PLANS:
        if plan.id == plan_id:
            return PayrollPlan(
                id=plan.id,
                name=plan.name,
                description=plan.description,
                stripe_price_id_env=plan.stripe_price_id_env,
                billing_interval=plan.billing_interval,
                max_employees=plan.max_employees,
                price_gbp_ex_vat=plan.price_gbp_ex_vat,
                features=plan.features,
            )
    return None


def list_payroll_plans() -> list[PayrollPlan]:
    db_plans = list_payroll_plans_from_db()
    if db_plans:
        return db_plans
    return [
        PayrollPlan(
            id=plan.id,
            name=plan.name,
            description=plan.description,
            stripe_price_id_env=plan.stripe_price_id_env,
            billing_interval=plan.billing_interval,
            max_employees=plan.max_employees,
            price_gbp_ex_vat=plan.price_gbp_ex_vat,
            features=plan.features,
        )
        for plan in DEFAULT_PAYROLL_PLANS
    ]


def resolve_stripe_price_id(plan: PayrollPlan) -> str | None:
    if plan.stripe_price_id:
        return plan.stripe_price_id
    if plan.stripe_price_id_env:
        return os.getenv(plan.stripe_price_id_env) or None
    return None
