-- Admin workspace: tenant profile fields, employees, document store

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS trading_name TEXT,
  ADD COLUMN IF NOT EXISTS company_number TEXT,
  ADD COLUMN IF NOT EXISTS registered_address TEXT,
  ADD COLUMN IF NOT EXISTS phone TEXT,
  ADD COLUMN IF NOT EXISTS signatory_name TEXT,
  ADD COLUMN IF NOT EXISTS signatory_title TEXT,
  ADD COLUMN IF NOT EXISTS signatory_email TEXT;

CREATE TABLE IF NOT EXISTS employees (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id),
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  email TEXT,
  job_title TEXT,
  start_date DATE,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'inactive', 'onboarding')),
  is_sponsored BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employees_tenant ON employees (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_employees_tenant_name ON employees (tenant_id, last_name, first_name);

CREATE TABLE IF NOT EXISTS tenant_documents (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id),
  title TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'general',
  document_url TEXT,
  notes TEXT,
  uploaded_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenant_documents_tenant
  ON tenant_documents (tenant_id, created_at DESC);
