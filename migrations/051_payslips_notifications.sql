-- Phase 1: payslip documents, pay period, rota publish + employee email prefs

ALTER TABLE employee_documents DROP CONSTRAINT IF EXISTS employee_documents_category_check;
ALTER TABLE employee_documents ADD CONSTRAINT employee_documents_category_check
  CHECK (category IN (
    'general', 'contract', 'id', 'rtw', 'qualification',
    'disciplinary', 'policy', 'payslip', 'other'
  ));

ALTER TABLE employee_documents
  ADD COLUMN IF NOT EXISTS pay_period TEXT;

CREATE INDEX IF NOT EXISTS idx_employee_documents_payslip
  ON employee_documents (tenant_id, employee_id, pay_period DESC NULLS LAST)
  WHERE category = 'payslip';

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS notify_on_rota_publish BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS notification_preferences JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS email_notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE;
