-- HR template versioning — legal updates, revision history, tenant sync tracking

ALTER TABLE hr_process_templates
  ADD COLUMN IF NOT EXISTS legal_basis TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS change_summary TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS content_sha256 TEXT NOT NULL DEFAULT '';

ALTER TABLE tenant_hr_templates
  ADD COLUMN IF NOT EXISTS based_on_platform_version TEXT,
  ADD COLUMN IF NOT EXISTS last_seen_platform_version TEXT;

CREATE TABLE IF NOT EXISTS hr_template_revisions (
  id BIGSERIAL PRIMARY KEY,
  template_id TEXT NOT NULL REFERENCES hr_process_templates(id),
  version TEXT NOT NULL,
  title TEXT NOT NULL,
  content_markdown TEXT NOT NULL,
  legal_basis TEXT NOT NULL DEFAULT '',
  change_summary TEXT NOT NULL DEFAULT '',
  content_sha256 TEXT NOT NULL,
  published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (template_id, version)
);

CREATE INDEX IF NOT EXISTS idx_hr_template_revisions_template
  ON hr_template_revisions (template_id, published_at DESC);
