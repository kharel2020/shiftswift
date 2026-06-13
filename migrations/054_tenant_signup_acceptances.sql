-- Audit trail for legal agreements accepted during self-service signup

CREATE TABLE IF NOT EXISTS tenant_signup_acceptances (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  accepted_eula BOOLEAN NOT NULL DEFAULT FALSE,
  accepted_payment_terms BOOLEAN NOT NULL DEFAULT FALSE,
  accepted_dpa BOOLEAN NOT NULL DEFAULT FALSE,
  accepted_service_scope BOOLEAN NOT NULL DEFAULT FALSE,
  eula_version TEXT NOT NULL DEFAULT '2026-06-08',
  payment_terms_version TEXT NOT NULL DEFAULT '2026-06-09',
  dpa_version TEXT NOT NULL DEFAULT '2026-06-08',
  holds_sponsor_licence BOOLEAN NOT NULL DEFAULT FALSE,
  sponsor_licence_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
  accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ip_address TEXT,
  user_agent TEXT,
  UNIQUE (tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_tenant_signup_acceptances_tenant
  ON tenant_signup_acceptances (tenant_id, accepted_at DESC);

COMMENT ON TABLE tenant_signup_acceptances IS 'Legal agreement acceptance captured at B2B self-service signup.';
