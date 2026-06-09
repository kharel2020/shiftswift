# Sponsor Licence Safeguards — Development Backlog (Priority)

ShiftSwift HR must actively enforce UK Sponsor Licence duties to protect clients' Sponsor Licences. **These items are P0 and must not be deprioritised.**

## P0 — Mandatory product safeguards

### 1. Right to Work (RTW) automations
- [x] Link to official UK Government Right to Work Checklist (`/compliance/sponsor-licence/checklist`)
- [x] Store dated RTW evidence as **immutable PDF** (`right_to_work_checks` + DB trigger)
- [x] SHA-256 integrity hash on upload
- [ ] Automated expiry flags + HR admin dashboard badges
- [x] Share code / IDSP verification endpoint (`POST /rtw-verify-share-code`) — mock when IDSP not configured

**Implementation:** `backend_stub/sponsor_licence_compliance.py`, migration `020_sponsor_licence_safeguards.sql`

### 2. 10-day absence trigger (sponsored workers)
- [x] Track consecutive **working-day** unexcused absences
- [x] Generate **day-9** alert before Home Office 10-working-day reporting threshold
- [x] Queue email/SMS notifications to HR admin
- [x] Typed absence reasons (paid annual leave, unpaid authorized, sick, bank holiday, unauthorized)
- [x] Admin UI to record absence days and view excused vs unexcused streaks
- [x] Working calendar API + admin UI for bank holidays / non-working days
- [ ] UI acknowledgement + "reported to Home Office" workflow

**Job:** `scripts/run_sponsor_compliance_jobs.sh` (schedule daily before 09:00 local)

### 3. SMS reporting change logs
- [x] Log changes to `job_title`, `salary`, `work_location`
- [x] 10-day SMS reporting deadline per change
- [x] Visual alert states: `open`, `due_soon`, `overdue`, `reported`
- [x] Hook into employee update API middleware (auto-log on PATCH)
- [x] Export pack for audit / Home Office evidence (JSON + PDF)

**Implementation:** `sponsor_sms_change_log` table + `/compliance/sponsor-licence/sms-changes`

### 4. Recruitment advertisement records (RLMT / audit evidence)
- [x] Store job advert records with **primary URL** and additional links
- [x] Platform tracking (GOV.UK Find a Job, Indeed, LinkedIn, careers site, etc.)
- [x] Link to official GOV.UK recruitment guidance
- [x] Compliance dashboard summary + admin UI table
- [ ] Attach screenshot/PDF evidence upload per advert
- [ ] Link advert records to recruitment `jobs` / CoS assignments automatically

**API:**
- `GET /compliance/sponsor-licence/advertisement-records`
- `POST /compliance/sponsor-licence/advertisement-records`
- `POST /compliance/sponsor-licence/advertisement-records/{id}/links`
- `GET /compliance/sponsor-licence/recruitment-links`

**Migration:** `021_recruitment_advertisement_records.sql`

## P0 — Mandatory contract clauses (EULA)

- [x] **Clause A:** Customer sole responsibility for sponsor licence duties
- [x] **Clause B:** No liability for licence revocation due to customer inaction

**Document:** `docs/eula_hr_module.md` — must be presented at HR module activation / signup.

## Operational requirements

1. Run migrations `020_sponsor_licence_safeguards.sql` and `021_recruitment_advertisement_records.sql` in all environments.
2. Mount `RTW_STORAGE_DIR` on durable, access-controlled storage with backup.
3. Schedule `run_sponsor_compliance_jobs.sh` via cron/systemd (see `docs/scheduling.md`).
4. Require HR admin role for compliance dashboard access.
5. Present EULA acceptance before enabling sponsored-worker tracking.

## References

- [Right to Work Checklist (GOV.UK)](https://www.gov.uk/government/publications/right-to-work-checklist)
- [GOV.UK Find a Job](https://www.gov.uk/find-a-job)
- [Recruit a skilled worker (GOV.UK)](https://www.gov.uk/guidance/recruit-a-skilled-worker)
- Home Office sponsor guidance — worker absences and SMS change reporting
