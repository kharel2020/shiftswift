-- Shift cover / swap requests

CREATE TABLE IF NOT EXISTS rota_shift_requests (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  rota_shift_id BIGINT NOT NULL REFERENCES rota_shifts(id) ON DELETE CASCADE,
  request_type TEXT NOT NULL CHECK (request_type IN ('cover', 'swap')),
  requester_employee_id BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  target_employee_id BIGINT REFERENCES employees(id) ON DELETE SET NULL,
  target_shift_id BIGINT REFERENCES rota_shifts(id) ON DELETE SET NULL,
  note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rota_shift_requests_tenant_status
  ON rota_shift_requests (tenant_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_rota_shift_requests_shift
  ON rota_shift_requests (rota_shift_id);
