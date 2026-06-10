-- On-server file storage for tenant and employee document records

ALTER TABLE tenant_documents
  ADD COLUMN IF NOT EXISTS storage_path TEXT,
  ADD COLUMN IF NOT EXISTS content_sha256 TEXT,
  ADD COLUMN IF NOT EXISTS content_type TEXT,
  ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;

ALTER TABLE employee_documents
  ADD COLUMN IF NOT EXISTS storage_path TEXT,
  ADD COLUMN IF NOT EXISTS content_sha256 TEXT,
  ADD COLUMN IF NOT EXISTS content_type TEXT,
  ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;

CREATE INDEX IF NOT EXISTS idx_tenant_documents_storage
  ON tenant_documents (tenant_id) WHERE storage_path IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_employee_documents_storage
  ON employee_documents (tenant_id, employee_id) WHERE storage_path IS NOT NULL;
