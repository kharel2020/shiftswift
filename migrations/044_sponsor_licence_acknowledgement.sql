-- Sponsor licence holder confirmation before compliance module use

ALTER TABLE tenants ADD COLUMN IF NOT EXISTS holds_sponsor_licence BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS sponsor_licence_acknowledged_at TIMESTAMPTZ;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS sponsor_licence_acknowledged_by VARCHAR(255);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS sponsor_licence_ack_version VARCHAR(32);
