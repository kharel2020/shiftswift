-- Cyber Essentials readiness: hashed app users + security audit trail

CREATE TABLE IF NOT EXISTS app_users (
  id BIGSERIAL PRIMARY KEY,
  username TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'hr', 'employee')),
  tenant_id BIGINT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  failed_login_attempts INT NOT NULL DEFAULT 0,
  locked_until TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (username)
);

CREATE INDEX IF NOT EXISTS idx_app_users_tenant ON app_users (tenant_id);

CREATE TABLE IF NOT EXISTS security_audit_events (
  id BIGSERIAL PRIMARY KEY,
  event_type TEXT NOT NULL,
  username TEXT,
  tenant_id BIGINT,
  ip_address TEXT,
  user_agent TEXT,
  success BOOLEAN NOT NULL DEFAULT FALSE,
  detail TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_security_audit_created ON security_audit_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_audit_event ON security_audit_events (event_type, created_at DESC);
