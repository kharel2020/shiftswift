-- Platform master ops — suspend, soft delete, internal notes

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS platform_status TEXT NOT NULL DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS platform_suspended_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS platform_suspended_by TEXT,
  ADD COLUMN IF NOT EXISTS platform_suspended_reason TEXT,
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS deleted_by TEXT,
  ADD COLUMN IF NOT EXISTS internal_notes TEXT NOT NULL DEFAULT '';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'tenants_platform_status_check'
  ) THEN
    ALTER TABLE tenants
      ADD CONSTRAINT tenants_platform_status_check
      CHECK (platform_status IN ('active', 'suspended'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_tenants_platform_status ON tenants (platform_status);
CREATE INDEX IF NOT EXISTS idx_tenants_deleted_at ON tenants (deleted_at) WHERE deleted_at IS NOT NULL;

COMMENT ON COLUMN tenants.platform_status IS 'Master admin access control — active or suspended.';
COMMENT ON COLUMN tenants.deleted_at IS 'Soft delete timestamp — tenant hidden from register, access blocked.';
