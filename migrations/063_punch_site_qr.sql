-- Premises QR clock-in tokens and punch method tracking

ALTER TABLE punch_sites
  ADD COLUMN IF NOT EXISTS site_clock_token TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_punch_sites_clock_token
  ON punch_sites (site_clock_token)
  WHERE site_clock_token IS NOT NULL;

ALTER TABLE time_punches
  ADD COLUMN IF NOT EXISTS punch_method TEXT NOT NULL DEFAULT 'gps';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'time_punches_punch_method_check'
  ) THEN
    ALTER TABLE time_punches
      ADD CONSTRAINT time_punches_punch_method_check
      CHECK (punch_method IN ('gps', 'site_qr', 'admin'));
  END IF;
END $$;

COMMENT ON COLUMN punch_sites.site_clock_token IS 'Secret token embedded in premises QR for indoor clock-in';
COMMENT ON COLUMN time_punches.punch_method IS 'How punch was verified: gps, site_qr, or admin override';
