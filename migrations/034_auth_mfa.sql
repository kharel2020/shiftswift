-- Two-factor authentication (TOTP) and login portal separation

ALTER TABLE app_users
  ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS totp_secret TEXT,
  ADD COLUMN IF NOT EXISTS mfa_enabled_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS login_portal TEXT NOT NULL DEFAULT 'business';

UPDATE app_users SET login_portal = 'master' WHERE role = 'admin';
UPDATE app_users SET login_portal = 'business' WHERE role IN ('hr', 'employee');

ALTER TABLE app_users DROP CONSTRAINT IF EXISTS app_users_login_portal_check;
ALTER TABLE app_users ADD CONSTRAINT app_users_login_portal_check
  CHECK (login_portal IN ('master', 'business'));

COMMENT ON COLUMN app_users.login_portal IS 'master = platform admin login only; business = tenant HR login';
