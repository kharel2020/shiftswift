-- Base + per active employee pricing (monthly cap)

ALTER TABLE subscription_plans
  ADD COLUMN IF NOT EXISTS base_price_gbp_ex_vat NUMERIC(10, 2),
  ADD COLUMN IF NOT EXISTS price_per_active_employee_gbp_ex_vat NUMERIC(10, 2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS monthly_cap_gbp_ex_vat NUMERIC(10, 2),
  ADD COLUMN IF NOT EXISTS stripe_seat_price_id_env TEXT,
  ADD COLUMN IF NOT EXISTS stripe_seat_price_id TEXT;

COMMENT ON COLUMN subscription_plans.base_price_gbp_ex_vat IS 'Fixed monthly platform fee ex VAT';
COMMENT ON COLUMN subscription_plans.price_per_active_employee_gbp_ex_vat IS 'Per active employee ex VAT (billed monthly)';
COMMENT ON COLUMN subscription_plans.monthly_cap_gbp_ex_vat IS 'Hard monthly cap ex VAT for base + per-head total';
