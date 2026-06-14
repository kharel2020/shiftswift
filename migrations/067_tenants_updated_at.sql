-- tenants.updated_at — required by master ops (suspend, soft delete, notes, billing)

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

COMMENT ON COLUMN tenants.updated_at IS 'Last change to tenant billing, platform status, or ops notes.';
