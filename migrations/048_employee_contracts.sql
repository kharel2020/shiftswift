-- Employment contracts (employer ↔ employee) — separate from platform tenant_contracts (MSA/DPA).

ALTER TABLE hr_process_templates
  ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'shiftswift',
  ADD COLUMN IF NOT EXISTS source_url TEXT,
  ADD COLUMN IF NOT EXISTS source_label TEXT;

CREATE TABLE IF NOT EXISTS employee_contracts (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id),
  employee_id BIGINT NOT NULL REFERENCES employees(id),
  template_id TEXT NOT NULL REFERENCES hr_process_templates(id),
  contract_number TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'generated'
    CHECK (status IN ('draft', 'generated', 'sent', 'signed', 'declined', 'expired')),
  platform_template_version TEXT NOT NULL DEFAULT '1.0',
  template_source TEXT NOT NULL DEFAULT 'shiftswift',
  template_source_url TEXT,
  generated_markdown TEXT,
  generated_html TEXT,
  employee_email TEXT,
  employee_name TEXT NOT NULL DEFAULT '',
  signing_token TEXT UNIQUE,
  signing_token_expires_at TIMESTAMPTZ,
  signature_name TEXT,
  signature_ip TEXT,
  signed_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  signed_storage_path TEXT,
  employee_document_id BIGINT REFERENCES employee_documents(id),
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employee_contracts_tenant
  ON employee_contracts (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_employee_contracts_employee
  ON employee_contracts (tenant_id, employee_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_employee_contracts_token
  ON employee_contracts (signing_token) WHERE signing_token IS NOT NULL;

CREATE TABLE IF NOT EXISTS employee_contract_events (
  id BIGSERIAL PRIMARY KEY,
  contract_id BIGINT NOT NULL REFERENCES employee_contracts(id) ON DELETE CASCADE,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id),
  event_type TEXT NOT NULL,
  actor TEXT,
  detail TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employee_contract_events_contract
  ON employee_contract_events (contract_id, created_at DESC);
