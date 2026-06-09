# B2B Stripe billing — ShiftSwift HR

## Recommended pricing model (restaurants, cafés, pubs)

**Use flat per-site pricing with employee bands**, not pure per-seat billing.

| Why flat per site | Why not per-seat only |
|-------------------|------------------------|
| Predictable monthly cost for owners | Feels punitive as headcount fluctuates |
| Matches how hospitality buys software | Hard to explain at signup |
| Easier VAT invoicing (one line item) | Stripe metered billing adds complexity |

### Suggested tiers (configured in `billing_config.py`)

| Plan | Ex VAT | Inc VAT (20%) | Staff cap | Billing |
|------|--------|---------------|-----------|---------|
| **Starter** | **£18.95/mo** | **£22.74/mo** | Up to 10 | Monthly |
| Medium | £49/mo | £58.80/mo | Up to 25 | Monthly |
| Growth | £79/mo | £94.80/mo | Up to 50 | Monthly |
| Starter annual | £189.50/yr | £227.40/yr | Up to 10 | Annual (~2 months free) |

VAT at 20% is calculated by **Stripe Tax** at checkout when `STRIPE_TAX_ENABLED=1`.

### Editable plans (change anytime)

Plans live in **`subscription_plans`**. Marketing and signup read from the API — SQL updates apply instantly:

```sql
UPDATE subscription_plans SET price_gbp_ex_vat = 18.95 WHERE id = 'site_starter_monthly';
```

Re-seed: `python3 scripts/seed_billing_catalog.py`

### Discount & referral codes

| Code | Effect |
|------|--------|
| `LAUNCH20` | 20% off |
| `CAFE10` | 10% off Starter |
| `WELCOME5` | £5 off |
| `REF-PUB` | 15% off (referral) |
| `REF-TRIAL` | +14 extra trial days |

Signup URL: `signup.html?discount=LAUNCH20&ref=REF-PUB`

Billing is **auto-created on registration** (Stripe customer + subscription with trial).

Optional later: multi-site bundle (e.g. 3 sites for £129/mo) — add a new Price in Stripe.

---

## Payroll add-on pricing (separate model)

Payroll is **not included** in platform tiers — it is a **second subscription line item** with its own employee bands.

| Payroll plan | Ex VAT | Inc VAT (20%) | Staff cap | Billing |
|--------------|--------|---------------|-----------|---------|
| **Payroll Starter** | **£24.95/mo** | **£29.94/mo** | Up to 10 | Monthly |
| Payroll Standard | £49/mo | £58.80/mo | Up to 25 | Monthly |
| Payroll Growth | £69/mo | £82.80/mo | Up to 50 | Monthly |

Plans live in **`payroll_plans`**. Signup and marketing read `/billing/plans` → `payroll_plans`.

```sql
UPDATE payroll_plans SET price_gbp_ex_vat = 24.95 WHERE id = 'payroll_starter_monthly';
```

Discount codes apply to the **platform plan only**; payroll is billed at list price unless you add payroll-specific coupons later.

Stripe env vars:

```bash
STRIPE_PRICE_PAYROLL_STARTER_MONTHLY=price_...
STRIPE_PRICE_PAYROLL_STANDARD_MONTHLY=price_...
STRIPE_PRICE_PAYROLL_GROWTH_MONTHLY=price_...
```

---

## Stripe Dashboard setup

1. **Products** → create "ShiftSwift HR Starter" (£18.95), "Medium" (£49), and "Growth" (£79) with recurring GBP prices.
2. **Settings → Tax** → enable Stripe Tax, register for UK VAT if you are VAT-registered.
3. **Settings → Billing** → enable invoices, customer emails, Customer Portal.
4. **Developers → Webhooks** → endpoint `https://api.yourdomain.com/billing/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`
5. Copy **Secret key** and **Webhook signing secret** to production `.env`.

---

## Environment variables

```bash
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_TAX_ENABLED=1
STRIPE_CURRENCY=gbp
STRIPE_PRICE_SITE_STARTER_MONTHLY=price_...
STRIPE_PRICE_SITE_MEDIUM_MONTHLY=price_...
STRIPE_PRICE_SITE_GROWTH_MONTHLY=price_...
STRIPE_PRICE_SITE_STARTER_ANNUAL=price_...
```

---

## API usage

```bash
# List plans (public)
curl http://localhost:3000/billing/plans

# Create checkout (authenticated owner/admin)
curl -X POST http://localhost:3000/billing/checkout-session \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": "site_starter_monthly",
    "tenant_id": 1,
    "billing_email": "accounts@restaurant.co.uk",
    "vat_number": "GB123456789",
    "success_url": "https://app.example.com/billing/success",
    "cancel_url": "https://app.example.com/billing/cancel"
  }'
```

---

## 14-day free trial & upgrade reminders

New signups (`POST /signup/start` with `start_trial: true`) receive **14 days** free (`BILLING_TRIAL_DAYS` in `.env`).

| Day | Automated email |
|-----|-----------------|
| 7 days left | Reminder to upgrade |
| 3 days left | Reminder to upgrade |
| 1 day left | Final reminder |
| Trial ended | Upgrade required — admin access paused until subscribed |

**Cron:** `scripts/run_platform_jobs.py` queues emails to `billing_email` and delivers via SMTP (`SMTP_*` in `.env`). Without SMTP, messages are logged to stdout for local dev.

**Upgrade:** Tenant admins click **Upgrade now** in admin (calls `POST /billing/upgrade`) → Stripe Checkout → `subscription_status = active`.

**Demo tenant (ID 1):** Seeded as `active` so local login is not blocked after 14 days.

```bash
# Check trial status
curl -H "Authorization: Bearer $TOKEN" -H "X-Tenant-Id: 1" http://localhost:3000/billing/status
```

Apply migration: `psql "$DATABASE_URL" -f migrations/031_trial_reminders.sql`

---

## UK Direct Debit (Bacs) via Stripe

ShiftSwift HR collects **UK Bacs Direct Debit mandates** through Stripe Checkout — no separate GoCardless integration required.

### Stripe Dashboard setup

1. Enable **Bacs Direct Debit** in Stripe → Settings → Payment methods  
2. Complete Stripe’s Bacs sun/indemnity requirements for your business  
3. Add webhook events: `checkout.session.completed`, `setup_intent.succeeded`, `mandate.updated`  
4. Set in `.env`:

```bash
STRIPE_PAYMENT_METHODS=bacs_debit,card
```

### Tenant flow

| Step | What happens |
|------|----------------|
| Signup / trial | Stripe Checkout **setup** session collects Bacs mandate (sort code + account) |
| Upgrade | Checkout **subscription** session offers Direct Debit or card |
| Admin → Payroll | **Set up Direct Debit** calls `POST /billing/direct-debit/mandate` |
| Webhook | Mandate status stored on tenant (`mandate_status`: pending → active) |

### API

```bash
# Mandate status on billing status
curl -H "Authorization: Bearer $TOKEN" -H "X-Tenant-Id: 1" \
  http://localhost:3000/billing/status

# Start Direct Debit mandate setup
curl -X POST -H "Authorization: Bearer $TOKEN" -H "X-Tenant-Id: 1" \
  http://localhost:3000/billing/direct-debit/mandate
```

Apply migration: `psql "$DATABASE_URL" -f migrations/032_direct_debit_mandate.sql`

**Note:** First Bacs payment can take ~3–7 working days. Stripe notifies customers per Bacs scheme rules.

### Direct Debit payment failure — grace period & licence hold

If a Direct Debit collection fails:

| Phase | Duration | Access | Email |
|-------|----------|--------|-------|
| **Warning** | `BILLING_DD_GRACE_DAYS` (default 7 days) | Full access continues | Failed + mid-grace + 1-day reminders |
| **Hold** | After grace expires | Admin API blocked (`402`) | Licence on hold notice |

Configure: `BILLING_DD_GRACE_DAYS=7` in `.env`

Stripe webhooks: `invoice.payment_failed`, `invoice.paid`, `customer.subscription.updated`

Cron: `run_platform_jobs.py` applies hold and sends grace reminders.

Migration: `psql "$DATABASE_URL" -f migrations/033_dd_payment_hold.sql`

---

## B2B refund policy (summary)

Business subscriptions are **non-refundable** except where required by law. No consumer 14-day cooling-off applies to B2B contracts. Full wording: `docs/b2b_payment_terms.md`.

---

## Per-seat vs flat — decision

For your market (small private hospitality), **flat per site wins**. Add employee bands (25 / 50) rather than charging £3 × every waiter. Per-seat works better for enterprise HR (100+ staff, central HR team) — not your initial segment.
