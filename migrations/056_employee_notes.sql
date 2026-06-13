-- HR internal and employee-visible notes on employee records

CREATE TABLE IF NOT EXISTS employee_notes (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  employee_id BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  visibility TEXT NOT NULL
    CHECK (visibility IN ('hr_internal', 'employee_visible')),
  body TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_by_role TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employee_notes_employee
  ON employee_notes (tenant_id, employee_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_employee_notes_portal
  ON employee_notes (tenant_id, employee_id, created_at DESC)
  WHERE visibility = 'employee_visible';

COMMENT ON TABLE employee_notes IS 'HR-only encrypted notes and messages shared with the employee portal.';
COMMENT ON COLUMN employee_notes.body IS 'Encrypted for hr_internal; plain text for employee_visible.';
