DROP TABLE IF EXISTS employee_documents;

ALTER TABLE employees
  DROP COLUMN IF EXISTS emergency_contact_relationship,
  DROP COLUMN IF EXISTS emergency_contact_phone,
  DROP COLUMN IF EXISTS emergency_contact_name,
  DROP COLUMN IF EXISTS probation_end_date,
  DROP COLUMN IF EXISTS employment_type,
  DROP COLUMN IF EXISTS department,
  DROP COLUMN IF EXISTS ni_number,
  DROP COLUMN IF EXISTS home_address,
  DROP COLUMN IF EXISTS date_of_birth,
  DROP COLUMN IF EXISTS phone;
