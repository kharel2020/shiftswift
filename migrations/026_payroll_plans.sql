-- Payroll module pricing — separate catalog from platform HR subscriptions

CREATE TABLE IF NOT EXISTS payroll_plans (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  billing_interval TEXT NOT NULL CHECK (billing_interval IN ('month', 'year')),
  max_employees INT NOT NULL,
  price_gbp_ex_vat NUMERIC(10, 2) NOT NULL,
  features JSONB NOT NULL DEFAULT '[]'::jsonb,
  stripe_price_id_env TEXT,
  stripe_price_id TEXT,
  sort_order INT NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS payroll_plan_id TEXT REFERENCES payroll_plans(id),
  ADD COLUMN IF NOT EXISTS payroll_enabled BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON TABLE payroll_plans IS 'Optional payroll add-on tiers — billed separately from platform subscription_plans.';
COMMENT ON COLUMN tenants.payroll_plan_id IS 'Selected payroll add-on plan, if any.';
COMMENT ON COLUMN tenants.payroll_enabled IS 'True when tenant subscribes to a payroll add-on.';
