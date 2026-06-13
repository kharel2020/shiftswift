-- Permitted roles label for punch sites (e.g. all, or comma-separated job titles)

ALTER TABLE punch_sites
  ADD COLUMN IF NOT EXISTS permitted_roles TEXT NOT NULL DEFAULT 'all';
