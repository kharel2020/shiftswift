-- Geofenced time punch — punch sites, assignments, punch records

CREATE TABLE IF NOT EXISTS punch_sites (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  address TEXT NOT NULL,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  radius_meters INTEGER NOT NULL DEFAULT 150
    CHECK (radius_meters >= 25 AND radius_meters <= 2000),
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_punch_sites_tenant ON punch_sites (tenant_id, is_active);

CREATE TABLE IF NOT EXISTS employee_punch_assignments (
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  employee_id BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  punch_site_id BIGINT NOT NULL REFERENCES punch_sites(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (employee_id, punch_site_id)
);

CREATE INDEX IF NOT EXISTS idx_employee_punch_assignments_site
  ON employee_punch_assignments (punch_site_id);

CREATE TABLE IF NOT EXISTS time_punches (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  employee_id BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  punch_site_id BIGINT NOT NULL REFERENCES punch_sites(id) ON DELETE RESTRICT,
  punch_type TEXT NOT NULL CHECK (punch_type IN ('in', 'out')),
  punched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  accuracy_meters DOUBLE PRECISION,
  distance_meters DOUBLE PRECISION NOT NULL,
  within_geofence BOOLEAN NOT NULL DEFAULT TRUE,
  app_username TEXT NOT NULL,
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_time_punches_tenant_day
  ON time_punches (tenant_id, punched_at DESC);

CREATE INDEX IF NOT EXISTS idx_time_punches_employee
  ON time_punches (tenant_id, employee_id, punched_at DESC);

COMMENT ON TABLE punch_sites IS 'Work locations with geofence radius for clock in/out';
COMMENT ON TABLE time_punches IS 'Employee clock punches validated against assigned punch sites';
