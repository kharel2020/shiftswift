-- Missed clock-in alerts — dedupe HR/employee notifications per published shift

CREATE TABLE IF NOT EXISTS rota_missed_punch_alerts (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  rota_shift_id BIGINT NOT NULL REFERENCES rota_shifts(id) ON DELETE CASCADE,
  employee_id BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  alert_type TEXT NOT NULL DEFAULT 'missed_clock_in'
    CHECK (alert_type IN ('missed_clock_in')),
  shift_date DATE NOT NULL,
  shift_start_at TIMESTAMPTZ NOT NULL,
  notified_hr BOOLEAN NOT NULL DEFAULT FALSE,
  notified_employee BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, rota_shift_id, alert_type)
);

CREATE INDEX IF NOT EXISTS idx_rota_missed_punch_alerts_tenant_day
  ON rota_missed_punch_alerts (tenant_id, shift_date DESC);

COMMENT ON TABLE rota_missed_punch_alerts IS
  'One row per shift when no clock-in was recorded within the grace period after start time';
