-- Leave requests + sponsor absence reporting reference

ALTER TABLE sponsor_absence_alerts
  ADD COLUMN IF NOT EXISTS home_office_report_reference TEXT,
  ADD COLUMN IF NOT EXISTS reported_at TIMESTAMPTZ;

ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS annual_leave_days NUMERIC(5,2) NOT NULL DEFAULT 28;

CREATE TABLE IF NOT EXISTS leave_requests (
  id BIGSERIAL PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  leave_type TEXT NOT NULL CHECK (leave_type IN ('annual', 'sick', 'unpaid', 'other')),
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  days_requested NUMERIC(5,2) NOT NULL,
  reason TEXT,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  review_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_leave_requests_tenant_status
  ON leave_requests (tenant_id, status, start_date DESC);

CREATE INDEX IF NOT EXISTS idx_leave_requests_employee
  ON leave_requests (employee_id, start_date DESC);

COMMENT ON TABLE leave_requests IS 'Employee leave and holiday requests — HR approval workflow.';
COMMENT ON COLUMN employees.annual_leave_days IS 'Annual leave allowance in working days for balance calculations.';
