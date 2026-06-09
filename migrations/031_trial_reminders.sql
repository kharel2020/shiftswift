-- Trial reminder tracking — avoid duplicate upgrade emails

CREATE TABLE IF NOT EXISTS trial_reminder_log (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  reminder_key TEXT NOT NULL CHECK (reminder_key IN ('7_day', '3_day', '1_day', 'expired')),
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, reminder_key)
);

CREATE INDEX IF NOT EXISTS idx_trial_reminder_tenant ON trial_reminder_log (tenant_id, sent_at DESC);

COMMENT ON TABLE trial_reminder_log IS 'One row per trial reminder type sent to each tenant.';
