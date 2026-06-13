-- Web Push subscriptions for employee PWAs + dedupe log for shift reminders

CREATE TABLE IF NOT EXISTS push_subscriptions (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  employee_id INT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  endpoint TEXT NOT NULL,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (employee_id, endpoint)
);

CREATE INDEX IF NOT EXISTS idx_push_subscriptions_tenant_employee
  ON push_subscriptions (tenant_id, employee_id);

CREATE TABLE IF NOT EXISTS push_notification_log (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  employee_id INT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  notification_key TEXT NOT NULL,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, employee_id, notification_key)
);

CREATE INDEX IF NOT EXISTS idx_push_notification_log_sent_at
  ON push_notification_log (sent_at DESC);
