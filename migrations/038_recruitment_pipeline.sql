-- Recruitment pipeline — vacancy workflow through offer accepted → employee onboarding

CREATE TABLE IF NOT EXISTS recruitment_vacancies (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  reference TEXT,
  job_title TEXT NOT NULL,
  department TEXT,
  location TEXT,
  job_description TEXT,
  required_skills TEXT,
  salary_range_min NUMERIC(12, 2),
  salary_range_max NUMERIC(12, 2),
  screening_keywords TEXT,
  knockout_questions TEXT,
  candidate_name TEXT,
  candidate_email TEXT,
  candidate_phone TEXT,
  candidate_cv_url TEXT,
  application_source TEXT,
  pipeline_notes TEXT,
  candidate_rating INTEGER CHECK (candidate_rating IS NULL OR (candidate_rating >= 1 AND candidate_rating <= 5)),
  interview_at TIMESTAMPTZ,
  interview_video_link TEXT,
  scorecard_notes TEXT,
  hiring_decision TEXT NOT NULL DEFAULT 'pending'
    CHECK (hiring_decision IN ('pending', 'hire', 'reject')),
  rejection_reason TEXT,
  offer_letter_url TEXT,
  offer_status TEXT NOT NULL DEFAULT 'draft'
    CHECK (offer_status IN ('draft', 'sent', 'accepted', 'rejected')),
  worker_type TEXT NOT NULL DEFAULT 'standard'
    CHECK (worker_type IN ('standard', 'sponsored')),
  current_stage TEXT NOT NULL DEFAULT 'vacancy_identified',
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'rejected', 'offer_accepted', 'onboarding_started', 'closed')),
  employee_id BIGINT REFERENCES employees(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recruitment_vacancies_tenant
  ON recruitment_vacancies (tenant_id, status, updated_at DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'recruitment_adverts_vacancy_fk'
  ) THEN
    ALTER TABLE recruitment_advertisement_records
      ADD CONSTRAINT recruitment_adverts_vacancy_fk
      FOREIGN KEY (vacancy_id) REFERENCES recruitment_vacancies(id) ON DELETE SET NULL;
  END IF;
EXCEPTION
  WHEN others THEN NULL;
END $$;
