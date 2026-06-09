-- Minimal local base schema for ShiftSwift HR dev install

CREATE TABLE IF NOT EXISTS tenants (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notifications (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  channel TEXT NOT NULL DEFAULT 'email',
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'queued',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO tenants (id, name)
SELECT 1, 'ShiftSwift HR Demo Tenant'
WHERE NOT EXISTS (SELECT 1 FROM tenants WHERE id = 1);

SELECT setval(pg_get_serial_sequence('tenants', 'id'), GREATEST((SELECT MAX(id) FROM tenants), 1));
