-- Employee portal GDPR consent captured when completing account setup

CREATE TABLE IF NOT EXISTS employee_portal_gdpr_consents (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  username TEXT NOT NULL,
  consent_version TEXT NOT NULL,
  employer_name TEXT,
  ip_address TEXT,
  user_agent TEXT,
  consented_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, username)
);

CREATE INDEX IF NOT EXISTS idx_employee_portal_gdpr_consents_user
  ON employee_portal_gdpr_consents (tenant_id, lower(username));

COMMENT ON TABLE employee_portal_gdpr_consents IS 'Employee acknowledgement that their employer manages personal data and privacy (UK GDPR).';
