-- UK Direct Debit (Stripe Bacs) mandate tracking per tenant

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS payment_method_type TEXT,
  ADD COLUMN IF NOT EXISTS stripe_payment_method_id TEXT,
  ADD COLUMN IF NOT EXISTS stripe_mandate_id TEXT,
  ADD COLUMN IF NOT EXISTS mandate_status TEXT,
  ADD COLUMN IF NOT EXISTS mandate_sort_code TEXT,
  ADD COLUMN IF NOT EXISTS mandate_account_last4 TEXT,
  ADD COLUMN IF NOT EXISTS mandate_confirmed_at TIMESTAMPTZ;

COMMENT ON COLUMN tenants.mandate_status IS 'Stripe Bacs mandate: pending, active, inactive, none';
