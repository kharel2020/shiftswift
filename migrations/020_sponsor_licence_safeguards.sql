-- Sponsor Licence mandatory safeguards (UK Home Office duties)
-- RTW immutability, 10-day absence triggers, SMS reporting change logs

CREATE TABLE IF NOT EXISTS employee_sponsor_profiles (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  employee_id BIGINT NOT NULL,
  is_sponsored_worker BOOLEAN NOT NULL DEFAULT FALSE,
  visa_type TEXT,
  cos_reference TEXT,
  sponsor_licence_number TEXT,
  work_location_site_id BIGINT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, employee_id)
);

CREATE TABLE IF NOT EXISTS right_to_work_checks (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  employee_id BIGINT NOT NULL,
  check_date DATE NOT NULL,
  check_method TEXT NOT NULL,
  gov_checklist_url TEXT NOT NULL DEFAULT 'https://www.gov.uk/government/publications/right-to-work-checklist',
  gov_checklist_version TEXT,
  checker_user_id TEXT,
  outcome TEXT NOT NULL CHECK (outcome IN ('pass', 'time_limited', 'fail')),
  expiry_date DATE,
  immutable_locked BOOLEAN NOT NULL DEFAULT TRUE,
  content_sha256 TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rtw_checks_tenant_employee ON right_to_work_checks (tenant_id, employee_id);
CREATE INDEX IF NOT EXISTS idx_rtw_checks_expiry ON right_to_work_checks (tenant_id, expiry_date);

-- Append-only enforcement: block updates/deletes once locked
CREATE OR REPLACE FUNCTION prevent_rtw_mutation()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    RAISE EXCEPTION 'right_to_work_checks records are immutable once stored';
  ELSIF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'right_to_work_checks records cannot be deleted';
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_rtw_immutable ON right_to_work_checks;
CREATE TRIGGER trg_rtw_immutable
  BEFORE UPDATE OR DELETE ON right_to_work_checks
  FOR EACH ROW EXECUTE FUNCTION prevent_rtw_mutation();

CREATE TABLE IF NOT EXISTS sponsor_working_calendar (
  tenant_id BIGINT NOT NULL,
  calendar_date DATE NOT NULL,
  is_working_day BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (tenant_id, calendar_date)
);

CREATE TABLE IF NOT EXISTS sponsored_absence_days (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  employee_id BIGINT NOT NULL,
  absence_date DATE NOT NULL,
  is_excused BOOLEAN NOT NULL DEFAULT FALSE,
  excuse_type TEXT,
  source TEXT NOT NULL DEFAULT 'attendance',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, employee_id, absence_date)
);

CREATE TABLE IF NOT EXISTS sponsor_absence_alerts (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  employee_id BIGINT NOT NULL,
  consecutive_working_days INTEGER NOT NULL,
  alert_day INTEGER NOT NULL DEFAULT 9,
  alert_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (alert_status IN ('pending', 'sent', 'acknowledged', 'reported')),
  triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notified_channels TEXT[] NOT NULL DEFAULT ARRAY['email'],
  home_office_report_required_by DATE,
  acknowledged_by TEXT,
  acknowledged_at TIMESTAMPTZ,
  UNIQUE (tenant_id, employee_id, triggered_at)
);

CREATE INDEX IF NOT EXISTS idx_sponsor_absence_alerts_status
  ON sponsor_absence_alerts (tenant_id, alert_status, triggered_at DESC);

CREATE TABLE IF NOT EXISTS sponsor_sms_change_log (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  employee_id BIGINT NOT NULL,
  field_name TEXT NOT NULL CHECK (field_name IN ('job_title', 'salary', 'work_location')),
  old_value TEXT,
  new_value TEXT,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  changed_by TEXT,
  sms_reporting_deadline DATE NOT NULL,
  alert_status TEXT NOT NULL DEFAULT 'open'
    CHECK (alert_status IN ('open', 'due_soon', 'overdue', 'reported', 'dismissed')),
  reported_at TIMESTAMPTZ,
  reported_by TEXT,
  report_reference TEXT,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_sponsor_sms_change_log_deadline
  ON sponsor_sms_change_log (tenant_id, alert_status, sms_reporting_deadline);

CREATE TABLE IF NOT EXISTS compliance_audit_events (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  event_type TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id BIGINT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_compliance_audit_tenant_created
  ON compliance_audit_events (tenant_id, created_at DESC);
