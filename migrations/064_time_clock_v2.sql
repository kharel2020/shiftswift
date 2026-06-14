-- Break punches, kiosk PIN, timesheet approvals, kiosk sessions

ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS kiosk_pin_hash TEXT;

ALTER TABLE time_punches DROP CONSTRAINT IF EXISTS time_punches_punch_type_check;
ALTER TABLE time_punches ADD CONSTRAINT time_punches_punch_type_check
  CHECK (punch_type IN ('in', 'out', 'break_start', 'break_end'));

ALTER TABLE time_punches DROP CONSTRAINT IF EXISTS time_punches_punch_method_check;
ALTER TABLE time_punches ADD CONSTRAINT time_punches_punch_method_check
  CHECK (punch_method IN ('gps', 'site_qr', 'admin', 'kiosk'));

CREATE TABLE IF NOT EXISTS timesheet_week_approvals (
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  week_start DATE NOT NULL,
  employee_id BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'rejected')),
  note TEXT,
  decided_by TEXT,
  decided_at TIMESTAMPTZ,
  PRIMARY KEY (tenant_id, week_start, employee_id)
);

CREATE INDEX IF NOT EXISTS idx_timesheet_approvals_week
  ON timesheet_week_approvals (tenant_id, week_start);

CREATE TABLE IF NOT EXISTS kiosk_punch_sessions (
  id BIGSERIAL PRIMARY KEY,
  session_token TEXT NOT NULL UNIQUE,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  employee_id BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  punch_site_id BIGINT NOT NULL REFERENCES punch_sites(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kiosk_sessions_token ON kiosk_punch_sessions (session_token);

COMMENT ON COLUMN employees.kiosk_pin_hash IS 'Bcrypt hash of 4–6 digit PIN for shared kiosk clock-in';
COMMENT ON TABLE timesheet_week_approvals IS 'Manager approval of weekly hours per employee';
COMMENT ON TABLE kiosk_punch_sessions IS 'Short-lived shared-tablet punch sessions';
