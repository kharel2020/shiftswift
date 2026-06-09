-- B2B tenant isolation, subscription billing hooks, RBAC roles, employee audit trail
-- HR platform is logically segregated from EPOS/hospitality transaction data.

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS platform TEXT NOT NULL DEFAULT 'hr',
  ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
  ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT,
  ADD COLUMN IF NOT EXISTS subscription_plan TEXT,
  ADD COLUMN IF NOT EXISTS subscription_status TEXT NOT NULL DEFAULT 'trialing',
  ADD COLUMN IF NOT EXISTS billing_email TEXT,
  ADD COLUMN IF NOT EXISTS vat_number TEXT,
  ADD COLUMN IF NOT EXISTS max_employees INT NOT NULL DEFAULT 25,
  ADD COLUMN IF NOT EXISTS data_region TEXT NOT NULL DEFAULT 'uk';

COMMENT ON COLUMN tenants.platform IS 'Always hr for this database — never mixed with EPOS commercial data.';
COMMENT ON COLUMN tenants.data_region IS 'Logical data residency marker for DPA disclosures.';

CREATE TABLE IF NOT EXISTS tenant_users (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id),
  username TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('owner', 'hr_manager', 'general_manager', 'supervisor', 'employee')),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, username)
);

CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant ON tenant_users (tenant_id);

CREATE TABLE IF NOT EXISTS employee_data_audit_log (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  actor_username TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('view', 'create', 'update', 'delete', 'export')),
  entity_type TEXT NOT NULL,
  entity_id BIGINT,
  field_name TEXT,
  old_value TEXT,
  new_value TEXT,
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employee_audit_tenant_created
  ON employee_data_audit_log (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_employee_audit_entity
  ON employee_data_audit_log (tenant_id, entity_type, entity_id);

-- Row-level guard: audit rows always belong to a valid tenant
CREATE OR REPLACE FUNCTION enforce_tenant_exists_for_audit()
RETURNS TRIGGER AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM tenants WHERE id = NEW.tenant_id) THEN
    RAISE EXCEPTION 'Invalid tenant_id for audit log';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_employee_audit_tenant ON employee_data_audit_log;
CREATE TRIGGER trg_employee_audit_tenant
  BEFORE INSERT ON employee_data_audit_log
  FOR EACH ROW EXECUTE FUNCTION enforce_tenant_exists_for_audit();

CREATE TABLE IF NOT EXISTS billing_events (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT REFERENCES tenants(id),
  stripe_event_id TEXT UNIQUE,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_billing_events_tenant ON billing_events (tenant_id, created_at DESC);
