-- Direct Debit payment failure — grace period, license hold, reminder log

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS payment_failed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS license_hold_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS license_state TEXT NOT NULL DEFAULT 'active';

COMMENT ON COLUMN tenants.license_state IS 'active | payment_warning | payment_hold | trial_expired';
COMMENT ON COLUMN tenants.payment_failed_at IS 'First failed Direct Debit / invoice in current failure cycle';
COMMENT ON COLUMN tenants.license_hold_at IS 'When software access was restricted after grace period';

CREATE TABLE IF NOT EXISTS payment_failure_reminder_log (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  failure_started_at TIMESTAMPTZ NOT NULL,
  reminder_key TEXT NOT NULL CHECK (
    reminder_key IN ('failed', 'grace_mid', 'grace_1_day', 'hold')
  ),
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, failure_started_at, reminder_key)
);

CREATE INDEX IF NOT EXISTS idx_payment_failure_reminders_tenant
  ON payment_failure_reminder_log (tenant_id, failure_started_at DESC);
