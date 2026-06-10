#!/usr/bin/env python3
"""Manual introducer commission report — reads referral_code on tenants; does not pay anyone."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend_stub"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend_stub" / ".env")
load_dotenv(ROOT / ".env")

import psycopg2

from partner_commission_service import INTRODUCER_CSV_FIELDS, fetch_introducer_commission_rows


def print_table(rows: list[dict[str, object]]) -> None:
    if not rows:
        print("No referred tenants found.")
        return

    by_partner: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        key = str(row["referral_code"])
        by_partner.setdefault(key, []).append(row)

    for code, items in sorted(by_partner.items()):
        partner = items[0].get("partner_name") or "Unknown"
        pct = items[0].get("commission_percent", 0)
        print(f"\n=== {code} — {partner} ({pct}% agreed commission) ===")
        total_commission = 0.0
        for row in items:
            est = row.get("estimated_commission_ex_vat")
            est_s = f"£{est:.2f}" if est is not None else "n/a"
            mrr = row.get("estimated_mrr_ex_vat")
            mrr_s = f"£{mrr:.2f}" if mrr is not None else "n/a"
            print(
                f"  tenant {row['tenant_id']:>4}  {row['business_name']!s:<32}  "
                f"status={row['subscription_status']:<12}  staff={row['active_employees']:>3}  "
                f"est MRR={mrr_s:<8}  est commission={est_s}"
            )
            if est is not None and row["subscription_status"] in {"active", "trialing"}:
                total_commission += float(est)
        print(f"  Subtotal estimated monthly commission (ex VAT): £{total_commission:.2f}")
        print("  → Confirm against Stripe invoices before paying introducer.")

    print("\nNOTE: Estimates use current active employee count + plan caps.")
    print("      Pay commissions manually per docs/partner_introducer_policy.md")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(INTRODUCER_CSV_FIELDS), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Introducer commission report (manual payouts)")
    parser.add_argument("--partner", help="Filter to one referral code, e.g. REF-SMITH-HR")
    parser.add_argument("--csv", help="Write CSV to this path")
    args = parser.parse_args()

    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required")

    conn = psycopg2.connect(url)
    try:
        rows = fetch_introducer_commission_rows(conn=conn, referral_code=args.partner)
    finally:
        conn.close()

    print_table(rows)
    if args.csv:
        write_csv(Path(args.csv), rows)


if __name__ == "__main__":
    main()
