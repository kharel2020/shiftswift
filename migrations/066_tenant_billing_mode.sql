-- Manual / offline billing for sales-led tenant provisioning

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS billing_mode TEXT NOT NULL DEFAULT 'stripe',
  ADD COLUMN IF NOT EXISTS billing_notes TEXT NOT NULL DEFAULT '';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'tenants_billing_mode_check'
  ) THEN
    ALTER TABLE tenants ADD CONSTRAINT tenants_billing_mode_check
      CHECK (billing_mode IN ('stripe', 'offline'));
  END IF;
END $$;

COMMENT ON COLUMN tenants.billing_mode IS 'stripe = self-serve Stripe billing; offline = invoiced or agreed pricing outside Stripe';
COMMENT ON COLUMN tenants.billing_notes IS 'Platform ops notes for custom pricing or invoice references';
