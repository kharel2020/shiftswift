-- Allow recruitment and contracts HR template categories from catalog.

ALTER TABLE hr_process_templates
  DROP CONSTRAINT IF EXISTS hr_process_templates_category_check;

ALTER TABLE hr_process_templates
  ADD CONSTRAINT hr_process_templates_category_check
  CHECK (category IN (
    'onboarding',
    'probation',
    'policy',
    'compliance',
    'offboarding',
    'disciplinary',
    'recruitment',
    'contracts'
  ));
