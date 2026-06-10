-- Password reset tokens for HR and employee self-service

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id BIGSERIAL PRIMARY KEY,
  username TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_password_reset_active
  ON password_reset_tokens (username, expires_at)
  WHERE used_at IS NULL;

COMMENT ON TABLE password_reset_tokens IS 'One-time password reset links for app_users';
