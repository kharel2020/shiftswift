-- HR digest when employees have not finished employee portal setup

CREATE TABLE IF NOT EXISTS portal_setup_reminder_log (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  reminder_date DATE NOT NULL,
  pending_count INT NOT NULL DEFAULT 0,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, reminder_date)
);

CREATE INDEX IF NOT EXISTS idx_portal_setup_reminder_tenant
  ON portal_setup_reminder_log (tenant_id, sent_at DESC);

COMMENT ON TABLE portal_setup_reminder_log IS 'At most one HR portal-setup digest email per tenant per day.';
