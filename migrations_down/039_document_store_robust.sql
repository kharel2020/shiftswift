ALTER TABLE tenant_documents DROP CONSTRAINT IF EXISTS tenant_documents_lifecycle_stage_check;
ALTER TABLE employee_documents DROP CONSTRAINT IF EXISTS employee_documents_category_check;
ALTER TABLE employee_documents DROP CONSTRAINT IF EXISTS employee_documents_lifecycle_stage_check;

ALTER TABLE tenant_documents
  DROP COLUMN IF EXISTS updated_at,
  DROP COLUMN IF EXISTS original_filename,
  DROP COLUMN IF EXISTS expires_at,
  DROP COLUMN IF EXISTS lifecycle_stage,
  DROP COLUMN IF EXISTS employee_id;

ALTER TABLE employee_documents
  DROP COLUMN IF EXISTS updated_at,
  DROP COLUMN IF EXISTS original_filename,
  DROP COLUMN IF EXISTS expires_at,
  DROP COLUMN IF EXISTS lifecycle_stage;

DROP INDEX IF EXISTS idx_employee_documents_category;
DROP INDEX IF EXISTS idx_employee_documents_stage;
DROP INDEX IF EXISTS idx_tenant_documents_category;
DROP INDEX IF EXISTS idx_tenant_documents_employee;
