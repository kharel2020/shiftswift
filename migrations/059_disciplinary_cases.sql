-- Disciplinary case management — encrypted notes and audit trail (Growth+)

CREATE TABLE IF NOT EXISTS disciplinary_cases (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  employee_id BIGINT NOT NULL REFERENCES employees(id),
  case_reference TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'investigation'
    CHECK (status IN ('investigation', 'hearing', 'appeal', 'closed')),
  misconduct_type TEXT NOT NULL,
  misconduct_type_other TEXT,
  severity TEXT NOT NULL DEFAULT 'medium'
    CHECK (severity IN ('low', 'medium', 'high', 'critical')),
  date_reported DATE NOT NULL,
  opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  closed_at TIMESTAMPTZ,
  close_outcome TEXT,
  opened_by TEXT NOT NULL,
  assigned_investigator TEXT,
  linked_absence_context TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, case_reference)
);

CREATE INDEX IF NOT EXISTS idx_disciplinary_cases_tenant
  ON disciplinary_cases (tenant_id, status, opened_at DESC);

CREATE TABLE IF NOT EXISTS disciplinary_case_notes (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  case_id BIGINT NOT NULL REFERENCES disciplinary_cases(id) ON DELETE CASCADE,
  encrypted_body TEXT NOT NULL,
  note_type TEXT NOT NULL DEFAULT 'investigation'
    CHECK (note_type IN ('investigation', 'hearing', 'appeal', 'system')),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_disciplinary_notes_case
  ON disciplinary_case_notes (tenant_id, case_id, created_at DESC);

CREATE TABLE IF NOT EXISTS disciplinary_case_audit (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  case_id BIGINT NOT NULL REFERENCES disciplinary_cases(id) ON DELETE CASCADE,
  action TEXT NOT NULL CHECK (action IN ('view', 'create', 'update', 'delete', 'upload', 'close')),
  actor_username TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  field_name TEXT,
  detail TEXT,
  ip_address TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_disciplinary_audit_case
  ON disciplinary_case_audit (tenant_id, case_id, created_at DESC);
