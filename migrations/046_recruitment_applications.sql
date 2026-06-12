-- Multiple applicants per vacancy + extended offer fields

CREATE TABLE IF NOT EXISTS recruitment_applications (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  vacancy_id BIGINT NOT NULL REFERENCES recruitment_vacancies(id) ON DELETE CASCADE,
  candidate_name TEXT NOT NULL,
  candidate_email TEXT,
  candidate_phone TEXT,
  candidate_cv_url TEXT,
  application_source TEXT,
  screening_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (screening_status IN ('pending', 'shortlisted', 'rejected')),
  screening_notes TEXT,
  match_score INTEGER CHECK (match_score IS NULL OR (match_score >= 0 AND match_score <= 100)),
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recruitment_applications_vacancy
  ON recruitment_applications (tenant_id, vacancy_id, screening_status, created_at DESC);

ALTER TABLE recruitment_vacancies
  ADD COLUMN IF NOT EXISTS offer_start_date DATE,
  ADD COLUMN IF NOT EXISTS offer_salary NUMERIC(12, 2),
  ADD COLUMN IF NOT EXISTS offer_hours_per_week NUMERIC(5, 2),
  ADD COLUMN IF NOT EXISTS offer_probation_weeks INTEGER,
  ADD COLUMN IF NOT EXISTS offer_sent_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS offer_notes TEXT;
