# Partner introducer policy — manual commissions only

**Internal — not for publication on the marketing site.**  
Share a one-page summary with signed introducers only (HR consultants, payroll bureaus, associations).

**Related:** [go_to_market_credibility.md](./go_to_market_credibility.md) · [b2b_stripe_billing_guide.md](./b2b_stripe_billing_guide.md)

---

## What we offer (and what we do not)

ShiftSwift HR runs an **introducer programme**, not a reseller or white-label programme.

| We do | We do not (yet) |
|-------|------------------|
| Give each introducer a unique **referral code** (`REF-…`) | Reseller portal or partner login |
| Apply a **customer benefit** at signup (discount, extra trial days) | Automatic commission payouts |
| **Track** which tenant signed up with which code | Let partners bill clients on our behalf |
| Pay introducers **manually** on agreed terms | Stripe Connect / revenue share automation |
| Support **one tenant per end client** (restaurant, care home, etc.) | “Manage all your clients in one partner account” |

### Typical scenario: HR specialist / consultancy

An HR consultant recommends ShiftSwift HR to their hospitality or sponsor-licence clients.

1. **Each end client** creates their **own** workspace (separate tenant) at signup.
2. Client enters the consultant’s code (e.g. `REF-SMITH-HR`) or uses `signup.html?ref=REF-SMITH-HR`.
3. Client gets the agreed **introducer benefit** (e.g. 10% off first year, or +14 trial days).
4. Consultant supports the client operationally (onboarding, RTW, compliance) — **support stays between consultant and client** unless we agree otherwise in writing.
5. **You** pay the consultant commission **manually** (bank transfer / invoice) using the monthly report script (below).

The consultant is **not** sublicensing the software. The **client** is the data controller; our MSA/DPA is with the **client business**, not the consultant (unless the consultant is the legal employer — rare).

---

## Who automates what today

### Automated in the product (no manual work)

| Step | Where |
|------|--------|
| Validate referral code at signup | `billing_promotions.validate_promotions()` |
| Apply customer discount / extra trial | Same + Stripe coupon if `stripe_coupon_id` set on code |
| Store `referral_code` on tenant | `tenants.referral_code` at signup |
| Audit row per signup | `promotion_redemptions` |
| Increment code usage count | `referral_codes.use_count` |
| Master admin list / test codes | Admin → Discount & referral codes |

### Manual (your ops — until Phase 2)

| Step | Owner | Tool |
|------|--------|------|
| Agree commission % and duration with introducer | You (founder) | Signed introducer agreement (email/PDF) |
| Create / edit referral code in DB | You or master admin | SQL or seed script |
| Calculate commission owed | You (finance) | `python3 scripts/partner_commission_report.py` |
| Pay introducer | You (finance) | Bank transfer + remittance email |
| Handle churn / refunds affecting commission | You | Spreadsheet + Stripe dashboard |

**Important:** `referrer_commission_percent` on `referral_codes` is **metadata for reporting only**. Nothing in the app calculates or pays commission automatically.

---

## Standard introducer terms (template — adjust per partner)

Use with a solicitor for anything binding. Suggested starting point:

1. **Customer benefit:** e.g. 10% off platform subscription for 12 months, or 14 extra trial days.
2. **Introducer commission:** e.g. **10% of net platform subscription** (ex VAT) for **12 months** from first paid invoice, while the client remains paying and active.
3. **Cap:** optional max per client per month (e.g. commission capped when client hits plan monthly cap).
4. **Exclusions:** no commission on refunded months, chargebacks, or clients who churn within 30 days (clawback optional).
5. **Payment:** quarterly in arrears, minimum £50 payout, UK bank account, introducer invoice required if VAT-registered.
6. **No exclusivity, no minimum sales, no reseller branding** unless separately agreed.
7. **Support:** client support is ShiftSwift HR unless white-glove tier is sold separately.

Record agreed terms in the `referral_codes` row (`partner_name`, `referrer_commission_percent`) and in your offline partner file.

---

## Creating an introducer code

After agreement signed:

```sql
INSERT INTO referral_codes (
  code, partner_name, reward_type, reward_value,
  referrer_commission_percent, max_uses, is_active
) VALUES (
  'REF-SMITH-HR',
  'Smith HR Consultancy',
  'percent',
  10,
  10.00,
  NULL,
  TRUE
);
```

Or extend `scripts/seed_billing_catalog.py` for known partners and re-seed.

**Signup link to send the introducer:**

`https://app.shiftswifthr.co.uk/signup.html?ref=REF-SMITH-HR&plan=compliance`

---

## Monthly / quarterly commission run

**Option A — Admin UI (platform master login):**

1. Sign in at **Master login** (tenant 999 / platform admin)
2. Open **Discount & referral codes**
3. Click **Export all introducers (CSV)** or **CSV** on a single referral code row
4. Confirm amounts against Stripe invoices → pay introducer → email remittance

**Option B — CLI:**

```bash
cd /path/to/shiftswifthr-api
source backend_stub/.venv/bin/activate
source scripts/load_env.sh && load_env_file backend_stub/.env
python3 scripts/partner_commission_report.py
python3 scripts/partner_commission_report.py --partner REF-SMITH-HR --csv reports/ref-smith-$(date +%Y-%m).csv
```

Review CSV → confirm amounts against Stripe invoices → pay introducer → email remittance.

---

## Public messaging rules

**Do say (to introducers privately):**

- “Introduce clients with your code; they get X; you earn Y% while they stay subscribed (paid quarterly).”

**Do not say (on website or ads):**

- “Become a reseller” / “Partner network” / “Earn passive income”
- Any commission % we are not prepared to pay manually within 30 days of quarter-end

On the **public** site, signup may mention an optional **introducer code** from your HR advisor — not a reseller programme.

---

## Phase 2 (build only when volume justifies it)

When you have **10+ active referred tenants** and manual payouts are painful:

1. **Commission ledger** table — month, tenant_id, referral_code, mrr_ex_vat, commission_due_gbp, status (pending/paid)
2. **Stripe webhook hook** — on `invoice.paid`, append ledger row using `tenants.referral_code`
3. **Partner report API** — read-only for master admin (still no partner login)
4. **Optional Stripe Connect** — only if paying many partners monthly

Until then: **referral tracking is automated; commission money is manual.**

---

## FAQ

**Can an HR company use one tenant for all their clients?**  
No. Each employer needs isolated tenant data (GDPR, sponsor licence, RTW). One tenant = one employer.

**Can the consultant access client tenants?**  
Not via a partner portal. Client can invite the consultant as an HR user on their tenant (normal RBAC) if the client agrees.

**Does BrightPay/Xero integration make them a “partner”?**  
Those are **payroll software partners** (integration), not sales introducers. Different meaning of “partner” on the site.

---

*Last updated: June 2026 — internal only; not committed to customer-facing legal pages.*
