-- Admin manual punches and audit fields on time punch records

ALTER TABLE time_punches
  ADD COLUMN IF NOT EXISTS admin_override BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS admin_note TEXT,
  ADD COLUMN IF NOT EXISTS recorded_by TEXT;
