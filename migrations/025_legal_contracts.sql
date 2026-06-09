-- Legal contracts: templates, generated documents, signing workflow

CREATE TABLE IF NOT EXISTS contract_templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  version TEXT NOT NULL DEFAULT '1.0',
  template_path TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_contracts (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id),
  template_id TEXT NOT NULL REFERENCES contract_templates(id),
  contract_number TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'generated', 'sent', 'signed', 'declined', 'expired')),
  customer_legal_name TEXT NOT NULL,
  customer_trading_name TEXT,
  company_number TEXT,
  registered_address TEXT,
  signatory_name TEXT,
  signatory_title TEXT,
  signatory_email TEXT NOT NULL,
  vat_number TEXT,
  plan_id TEXT,
  plan_name TEXT,
  plan_price_gbp_ex_vat NUMERIC(10, 2),
  effective_date DATE NOT NULL DEFAULT CURRENT_DATE,
  generated_html TEXT,
  generated_pdf_path TEXT,
  signed_pdf_path TEXT,
  signature_name TEXT,
  signature_ip TEXT,
  signed_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  signing_token TEXT UNIQUE,
  signing_token_expires_at TIMESTAMPTZ,
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenant_contracts_tenant ON tenant_contracts (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tenant_contracts_status ON tenant_contracts (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_tenant_contracts_token ON tenant_contracts (signing_token) WHERE signing_token IS NOT NULL;

CREATE TABLE IF NOT EXISTS contract_events (
  id BIGSERIAL PRIMARY KEY,
  contract_id BIGINT NOT NULL REFERENCES tenant_contracts(id) ON DELETE CASCADE,
  tenant_id BIGINT NOT NULL,
  event_type TEXT NOT NULL,
  actor TEXT,
  detail TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contract_events_contract ON contract_events (contract_id, created_at DESC);
