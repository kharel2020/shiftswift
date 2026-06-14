-- Platform master admin audit trail (impersonation, billing ops, support actions)

CREATE TABLE IF NOT EXISTS master_audit_log (
  id BIGSERIAL PRIMARY KEY,
  master_username TEXT NOT NULL,
  action TEXT NOT NULL,
  target_tenant_id BIGINT REFERENCES tenants(id) ON DELETE SET NULL,
  ip_address TEXT,
  user_agent TEXT,
  detail JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_master_audit_created ON master_audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_master_audit_action ON master_audit_log (action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_master_audit_tenant ON master_audit_log (target_tenant_id, created_at DESC);

COMMENT ON TABLE master_audit_log IS 'Immutable audit trail for platform master admin actions.';
