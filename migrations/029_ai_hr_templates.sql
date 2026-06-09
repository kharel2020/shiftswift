-- AI assistant settings + HR / onboarding process templates (platform + tenant copies)

ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS ai_assistant_enabled BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS hr_process_templates (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL
    CHECK (category IN ('onboarding', 'probation', 'policy', 'compliance', 'offboarding', 'disciplinary')),
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  content_markdown TEXT NOT NULL,
  version TEXT NOT NULL DEFAULT '1.0',
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_hr_templates (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id),
  template_id TEXT NOT NULL REFERENCES hr_process_templates(id),
  title TEXT NOT NULL,
  content_markdown TEXT NOT NULL,
  version TEXT NOT NULL DEFAULT '1.0',
  updated_by TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, template_id)
);

CREATE INDEX IF NOT EXISTS idx_tenant_hr_templates_tenant
  ON tenant_hr_templates (tenant_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS ai_assistant_log (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id),
  username TEXT NOT NULL,
  action TEXT NOT NULL,
  template_id TEXT,
  prompt_excerpt TEXT,
  provider TEXT,
  model TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_assistant_log_tenant
  ON ai_assistant_log (tenant_id, created_at DESC);
