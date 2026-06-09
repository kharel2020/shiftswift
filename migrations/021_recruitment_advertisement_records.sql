-- Recruitment advertisement records (sponsor licence / RLMT evidence)
-- Stores job advert details and links for audit and Home Office inspections.

CREATE TABLE IF NOT EXISTS recruitment_advertisement_records (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  job_reference TEXT,
  job_title TEXT NOT NULL,
  soc_code TEXT,
  vacancy_id BIGINT,
  platform TEXT NOT NULL,
  advert_url TEXT NOT NULL,
  advert_reference TEXT,
  posted_date DATE NOT NULL,
  closing_date DATE,
  is_sponsored_vacancy BOOLEAN NOT NULL DEFAULT TRUE,
  rlmt_applicable BOOLEAN NOT NULL DEFAULT TRUE,
  minimum_advertising_days INTEGER DEFAULT 28,
  additional_links JSONB NOT NULL DEFAULT '[]'::jsonb,
  evidence_storage_path TEXT,
  notes TEXT,
  record_status TEXT NOT NULL DEFAULT 'active'
    CHECK (record_status IN ('active', 'closed', 'archived')),
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recruitment_adverts_tenant_posted
  ON recruitment_advertisement_records (tenant_id, posted_date DESC);

CREATE INDEX IF NOT EXISTS idx_recruitment_adverts_tenant_status
  ON recruitment_advertisement_records (tenant_id, record_status, closing_date);

CREATE TABLE IF NOT EXISTS recruitment_advertisement_links (
  id BIGSERIAL PRIMARY KEY,
  advert_record_id BIGINT NOT NULL REFERENCES recruitment_advertisement_records(id) ON DELETE CASCADE,
  tenant_id BIGINT NOT NULL,
  link_label TEXT NOT NULL,
  link_url TEXT NOT NULL,
  link_type TEXT NOT NULL DEFAULT 'listing'
    CHECK (link_type IN ('listing', 'screenshot', 'archive', 'other')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recruitment_advert_links_record
  ON recruitment_advertisement_links (tenant_id, advert_record_id);
