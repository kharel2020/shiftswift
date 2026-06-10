-- Weekly rotas and shift assignments (live rota builder)

CREATE TABLE IF NOT EXISTS rota_weeks (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  week_start DATE NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
  published_at TIMESTAMPTZ,
  created_by TEXT,
  updated_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, week_start),
  CHECK (EXTRACT(ISODOW FROM week_start) = 1)
);

CREATE INDEX IF NOT EXISTS idx_rota_weeks_tenant ON rota_weeks (tenant_id, week_start DESC);

CREATE TABLE IF NOT EXISTS rota_shifts (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  rota_week_id BIGINT NOT NULL REFERENCES rota_weeks(id) ON DELETE CASCADE,
  employee_id BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  shift_date DATE NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  role_label TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (start_time <> end_time)
);

CREATE INDEX IF NOT EXISTS idx_rota_shifts_week_day
  ON rota_shifts (rota_week_id, shift_date, start_time);

CREATE INDEX IF NOT EXISTS idx_rota_shifts_employee_day
  ON rota_shifts (tenant_id, employee_id, shift_date);

COMMENT ON TABLE rota_weeks IS 'One rota per tenant per ISO week (Monday start)';
COMMENT ON TABLE rota_shifts IS 'Shift assignments linked to a rota week';
