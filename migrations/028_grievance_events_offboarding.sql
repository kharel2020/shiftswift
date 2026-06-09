-- Grievance module, domain events, offboarding, employee/compliance unification

ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS salary NUMERIC(12, 2),
  ADD COLUMN IF NOT EXISTS work_location TEXT,
  ADD COLUMN IF NOT EXISTS termination_date DATE,
  ADD COLUMN IF NOT EXISTS termination_reason TEXT;

ALTER TABLE employees DROP CONSTRAINT IF EXISTS employees_status_check;
ALTER TABLE employees ADD CONSTRAINT employees_status_check
  CHECK (status IN ('active', 'inactive', 'onboarding', 'suspended', 'terminated'));

ALTER TABLE employee_sponsor_profiles
  ADD COLUMN IF NOT EXISTS visa_expiry_date DATE,
  ADD COLUMN IF NOT EXISTS share_code TEXT,
  ADD COLUMN IF NOT EXISTS rtw_status TEXT NOT NULL DEFAULT 'pending';

CREATE TABLE IF NOT EXISTS domain_events (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  event_type TEXT NOT NULL,
  entity_type TEXT,
  entity_id BIGINT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  actor_username TEXT,
  actor_role TEXT,
  processed BOOLEAN NOT NULL DEFAULT FALSE,
  processed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_domain_events_unprocessed
  ON domain_events (processed, created_at) WHERE processed = FALSE;

CREATE INDEX IF NOT EXISTS idx_domain_events_tenant
  ON domain_events (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS webhook_subscriptions (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  name TEXT NOT NULL,
  target_url TEXT NOT NULL,
  event_types TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  secret TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_tenant
  ON webhook_subscriptions (tenant_id, is_active);

CREATE TABLE IF NOT EXISTS grievance_cases (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  employee_id BIGINT NOT NULL REFERENCES employees(id),
  case_reference TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'investigation'
    CHECK (status IN ('investigation', 'hearing', 'appeal', 'closed')),
  allegation_type TEXT NOT NULL,
  opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  closed_at TIMESTAMPTZ,
  close_outcome TEXT,
  acas_deadline DATE,
  appeal_deadline DATE,
  is_anonymous_to_manager BOOLEAN NOT NULL DEFAULT FALSE,
  linked_absence_context TEXT,
  opened_by TEXT NOT NULL,
  assigned_investigator TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, case_reference)
);

CREATE INDEX IF NOT EXISTS idx_grievance_cases_tenant
  ON grievance_cases (tenant_id, status, opened_at DESC);

CREATE TABLE IF NOT EXISTS grievance_case_notes (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  case_id BIGINT NOT NULL REFERENCES grievance_cases(id) ON DELETE CASCADE,
  encrypted_body TEXT NOT NULL,
  note_type TEXT NOT NULL DEFAULT 'investigation'
    CHECK (note_type IN ('investigation', 'hearing', 'appeal', 'system')),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_grievance_notes_case
  ON grievance_case_notes (tenant_id, case_id, created_at DESC);

CREATE TABLE IF NOT EXISTS grievance_case_audit (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  case_id BIGINT NOT NULL REFERENCES grievance_cases(id) ON DELETE CASCADE,
  action TEXT NOT NULL CHECK (action IN ('view', 'create', 'update', 'delete', 'upload', 'close')),
  actor_username TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  field_name TEXT,
  detail TEXT,
  ip_address TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_grievance_audit_case
  ON grievance_case_audit (tenant_id, case_id, created_at DESC);

CREATE TABLE IF NOT EXISTS acas_milestones (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  case_id BIGINT NOT NULL REFERENCES grievance_cases(id) ON DELETE CASCADE,
  milestone_type TEXT NOT NULL,
  due_date DATE NOT NULL,
  completed_at TIMESTAMPTZ,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_acas_milestones_due
  ON acas_milestones (tenant_id, due_date) WHERE completed_at IS NULL;

CREATE TABLE IF NOT EXISTS sponsor_reporting_triggers (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  employee_id BIGINT NOT NULL,
  trigger_type TEXT NOT NULL,
  source_module TEXT NOT NULL,
  source_entity_type TEXT,
  source_entity_id BIGINT,
  description TEXT NOT NULL,
  deadline_date DATE NOT NULL,
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'acknowledged', 'reported', 'dismissed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reported_at TIMESTAMPTZ,
  reported_by TEXT,
  report_reference TEXT
);

CREATE INDEX IF NOT EXISTS idx_sponsor_reporting_triggers_open
  ON sponsor_reporting_triggers (tenant_id, status, deadline_date);

CREATE TABLE IF NOT EXISTS offboarding_workflows (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  employee_id BIGINT NOT NULL,
  grievance_case_id BIGINT REFERENCES grievance_cases(id),
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'in_progress'
    CHECK (status IN ('in_progress', 'completed', 'cancelled')),
  acas_appeal_deadline DATE,
  sponsorship_cessation_required BOOLEAN NOT NULL DEFAULT FALSE,
  sponsorship_cessation_reported_at TIMESTAMPTZ,
  sponsorship_cessation_reference TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_offboarding_tenant
  ON offboarding_workflows (tenant_id, status, started_at DESC);
