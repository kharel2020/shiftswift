-- Allow portal invite events in employee_data_audit_log

ALTER TABLE employee_data_audit_log DROP CONSTRAINT IF EXISTS employee_data_audit_log_action_check;
ALTER TABLE employee_data_audit_log ADD CONSTRAINT employee_data_audit_log_action_check
  CHECK (action IN ('view', 'create', 'update', 'delete', 'export', 'invite'));

COMMENT ON COLUMN employee_data_audit_log.action IS 'Includes invite for employee portal provisioning.';
