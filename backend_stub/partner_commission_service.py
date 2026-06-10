"""Introducer commission estimates for manual partner payouts."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from billing_pricing import calculate_monthly_quote, plan_base_price, plan_per_head_price
from billing_plans import get_plan

INTRODUCER_CSV_FIELDS = (
    "tenant_id",
    "business_name",
    "billing_email",
    "referral_code",
    "partner_name",
    "commission_percent",
    "customer_reward",
    "plan_id",
    "plan_name",
    "subscription_status",
    "active_employees",
    "estimated_mrr_ex_vat",
    "estimated_commission_ex_vat",
    "trial_ends_at",
    "billing_created_at",
    "pricing_note",
    "report_generated_at",
)


def _active_employee_count(cur: Any, tenant_id: int) -> int:
    cur.execute(
        """
        SELECT COUNT(*) FROM employees
        WHERE tenant_id = %s AND status IN ('active', 'onboarding', 'suspended')
        """,
        (tenant_id,),
    )
    return int(cur.fetchone()[0])


def _estimate_mrr_ex_vat(cur: Any, tenant_id: int, plan_id: str | None) -> float | None:
    if not plan_id:
        return None
    plan = get_plan(plan_id)
    if not plan:
        return None
    headcount = _active_employee_count(cur, tenant_id)
    quote = calculate_monthly_quote(plan, active_employees=headcount)
    return float(quote["total_gbp_ex_vat"])


def fetch_introducer_commission_rows(
    *,
    conn: Any,
    referral_code: str | None = None,
) -> list[dict[str, object]]:
    generated_at = datetime.now(timezone.utc).isoformat()
    with conn.cursor() as cur:
        sql = """
            SELECT
              t.id,
              t.business_name,
              t.billing_email,
              t.referral_code,
              rc.partner_name,
              rc.referrer_commission_percent,
              rc.reward_type,
              rc.reward_value,
              t.subscription_plan,
              t.subscription_status,
              t.trial_ends_at,
              t.billing_created_at
            FROM tenants t
            LEFT JOIN referral_codes rc ON upper(rc.code) = upper(t.referral_code)
            WHERE t.referral_code IS NOT NULL
              AND trim(t.referral_code) <> ''
        """
        params: tuple[Any, ...] = ()
        if referral_code:
            sql += " AND upper(t.referral_code) = upper(%s)"
            params = (referral_code.strip(),)
        sql += " ORDER BY t.referral_code, t.id"

        cur.execute(sql, params)
        rows: list[dict[str, object]] = []
        for row in cur.fetchall():
            tenant_id = int(row[0])
            plan_id = row[8]
            mrr = _estimate_mrr_ex_vat(cur, tenant_id, plan_id)
            commission_pct = float(row[5]) if row[5] is not None else 0.0
            commission_est = round(mrr * commission_pct / 100, 2) if mrr is not None else None
            plan = get_plan(plan_id) if plan_id else None
            rows.append(
                {
                    "tenant_id": tenant_id,
                    "business_name": row[1],
                    "billing_email": row[2],
                    "referral_code": row[3],
                    "partner_name": row[4],
                    "commission_percent": commission_pct,
                    "customer_reward": f"{row[6]} {row[7]}" if row[6] else "",
                    "plan_id": plan_id,
                    "plan_name": plan.name if plan else "",
                    "subscription_status": row[9],
                    "active_employees": _active_employee_count(cur, tenant_id),
                    "estimated_mrr_ex_vat": mrr,
                    "estimated_commission_ex_vat": commission_est,
                    "trial_ends_at": row[10].isoformat() if row[10] else "",
                    "billing_created_at": row[11].isoformat() if row[11] else "",
                    "pricing_note": (
                        f"£{plan_base_price(plan):.2f} + £{plan_per_head_price(plan):.2f}/head"
                        if plan and plan_per_head_price(plan) > 0
                        else ""
                    ),
                    "report_generated_at": generated_at,
                }
            )
        return rows


def build_introducer_commission_csv(rows: list[dict[str, object]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(INTRODUCER_CSV_FIELDS), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: "" if row.get(key) is None else row[key]
                for key in INTRODUCER_CSV_FIELDS
            }
        )
    return buffer.getvalue()


def introducer_export_filename(*, referral_code: str | None = None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if referral_code:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in referral_code.strip())
        return f"shiftswift-introducer-{safe}-{stamp}.csv"
    return f"shiftswift-introducers-all-{stamp}.csv"
