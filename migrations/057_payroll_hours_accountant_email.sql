-- Automated monthly working-hours report to payroll accountant

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS payroll_accountant_email TEXT,
  ADD COLUMN IF NOT EXISTS payroll_hours_report_enabled BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS payroll_hours_report_log (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  recipient_email TEXT NOT NULL,
  employee_count INT NOT NULL DEFAULT 0,
  total_hours NUMERIC(10, 2),
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_payroll_hours_report_log_tenant
  ON payroll_hours_report_log (tenant_id, sent_at DESC);

COMMENT ON COLUMN tenants.payroll_accountant_email IS 'Payroll bureau or accountant email for monthly hours PDF.';
COMMENT ON COLUMN tenants.payroll_hours_report_enabled IS 'When true, send previous month hours PDF on the 1st of each month.';
