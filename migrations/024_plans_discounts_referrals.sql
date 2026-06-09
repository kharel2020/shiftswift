-- Editable subscription plans, discount codes, referral codes, tenant promo tracking

CREATE TABLE IF NOT EXISTS subscription_plans (
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

CREATE TABLE IF NOT EXISTS discount_codes (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL DEFAULT '',
  discount_type TEXT NOT NULL CHECK (discount_type IN ('percent', 'fixed_gbp')),
  discount_value NUMERIC(10, 2) NOT NULL,
  stripe_coupon_id TEXT,
  valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  valid_until TIMESTAMPTZ,
  max_redemptions INT,
  redemption_count INT NOT NULL DEFAULT 0,
  applicable_plan_ids TEXT[],
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS referral_codes (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  partner_name TEXT NOT NULL,
  reward_type TEXT NOT NULL CHECK (reward_type IN ('percent', 'fixed_gbp', 'trial_days')),
  reward_value NUMERIC(10, 2) NOT NULL,
  referrer_commission_percent NUMERIC(5, 2) NOT NULL DEFAULT 0,
  stripe_coupon_id TEXT,
  max_uses INT,
  use_count INT NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS promotion_redemptions (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id),
  discount_code TEXT,
  referral_code TEXT,
  plan_id TEXT NOT NULL,
  discount_applied_gbp NUMERIC(10, 2) NOT NULL DEFAULT 0,
  extra_trial_days INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS discount_code TEXT,
  ADD COLUMN IF NOT EXISTS referral_code TEXT,
  ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS billing_created_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_discount_codes_active ON discount_codes (code) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_referral_codes_active ON referral_codes (code) WHERE is_active = TRUE;
