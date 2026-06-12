-- Grievance case enhancements — date received, ACAS notification, severity, allegation other

ALTER TABLE grievance_cases
  ADD COLUMN IF NOT EXISTS date_received DATE,
  ADD COLUMN IF NOT EXISTS acas_notification_date DATE,
  ADD COLUMN IF NOT EXISTS allegation_type_other TEXT,
  ADD COLUMN IF NOT EXISTS severity TEXT NOT NULL DEFAULT 'medium'
    CHECK (severity IN ('low', 'medium', 'high', 'critical'));

UPDATE grievance_cases
SET date_received = COALESCE(date_received, opened_at::date)
WHERE date_received IS NULL;
