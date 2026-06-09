# ShiftSwift HR — Backend Setup Guide

This guide helps clients and integrators deploy the modular FastAPI backend.

## Architecture overview

```
                    ┌─────────────────────────┐
                    │   Core Employee DB      │
                    │   (employees table)     │
                    └───────────┬─────────────┘
                                │
           ┌────────────────────┼────────────────────┐
           ▼                    ▼                    ▼
   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
   │  Compliance   │   │  Grievance    │   │  Offboarding  │
   │  RTW / SMS    │   │  ACAS cases   │   │  Leaver flows │
   └───────┬───────┘   └───────┬───────┘   └───────┬───────┘
           │                   │                   │
           └───────────────────┼───────────────────┘
                               ▼
                    ┌─────────────────────────┐
                    │   Domain Event Bus      │
                    │   (domain_events table) │
                    └───────────┬─────────────┘
                               ▼
                    ┌─────────────────────────┐
                    │ Webhooks / Notifications│
                    └─────────────────────────┘
```

## 1. Prerequisites

- PostgreSQL 14+
- Python 3.11+
- Optional: Stripe account for billing

## 2. Install

```bash
git clone <repo>
cd shiftswifthr/backend_stub
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 3. Configure environment

| Variable | Required | Module |
|----------|----------|--------|
| `DATABASE_URL` | Yes | All |
| `JWT_SECRET` | Yes | Auth |
| `ENCRYPTION_KEY` | Yes (grievance) | Grievance — 64 hex chars (32 bytes) |
| `RTW_STORAGE_DIR` | Yes (compliance) | RTW PDF storage path |
| `CORS_ALLOW_ORIGINS` | Yes | Frontend access |
| `STRIPE_SECRET_KEY` | Billing only | Stripe checkout |
| `STRIPE_WEBHOOK_SECRET` | Billing only | Stripe webhooks |
| `IDSP_API_KEY`, `IDSP_API_URL` | Optional | Live IDSP RTW (mock if unset) |
| `SMTP_HOST`, `SMTP_FROM` | Optional | Notification delivery |
| `COMPLIANCE_ALERT_EMAIL` | Optional | Default compliance alert recipient |
| `AI_ENABLED`, `GEMINI_API_KEY` | Optional | AI document assistant (Gemini 2.0 Flash recommended) |
| `OPENAI_API_KEY` | Optional | AI fallback provider (`AI_PROVIDER=openai`) |

Generate keys:

```bash
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))"
python -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_hex(32))"
```

## 4. Run migrations

Apply in numeric order:

```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/shiftswift_hr
for f in migrations/0*.sql migrations/02*.sql; do
  psql "$DATABASE_URL" -f "$f"
done
```

Critical migrations for compliance + grievance:

- `020` — sponsor licence safeguards
- `021` — recruitment adverts
- `027` — employees admin workspace
- `028` — grievance, events, offboarding

## 5. Start the API

```bash
cd backend_stub
uvicorn main:app --host 0.0.0.0 --port 3000
```

Discovery endpoints:

- `GET /health` — liveness
- `GET /setup/status` — security flags
- `GET /setup/modules` — module catalog with setup requirements

## 6. Schedule background jobs

Add to crontab (run before 09:00 UK time):

```cron
0 1 * * * cd /path/to/shiftswifthr && DATABASE_URL=... .venv/bin/python scripts/run_platform_jobs.py >> /var/log/shiftswift-jobs.log 2>&1
```

Jobs include:

- Day-9 sponsor absence alerts
- SMS change status refresh (open → due_soon → overdue)
- Visa expiry warnings (90/60/30/7 days)
- RTW expiry scan
- Pending domain event processing

## 7. Module API reference

### Employees (`/admin/employees`)

Core workforce records. Updates to `job_title`, `salary`, or `work_location` on sponsored workers auto-log SMS reporting entries.

Statuses: `active`, `inactive`, `onboarding`, `suspended`, `terminated`.

### Compliance (`/compliance/sponsor-licence`)

| Endpoint | Description |
|----------|-------------|
| `POST /rtw-checks` | Upload immutable RTW PDF |
| `GET /absence-types` | Catalog of paid/unpaid/authorized absence types |
| `GET /absence-days` | List recorded absence days |
| `POST /absence-days` | Record sponsored absence day (`excuse_type` drives excused vs unexcused) |
| `DELETE /absence-days/{employee_id}/{date}` | Remove an absence day record |
| `GET /absence-streaks` | Per-worker unexcused streak + paid/unpaid leave counts |
| `GET /working-calendar` | List tenant working/non-working days |
| `PUT /working-calendar` | Upsert bank holidays / site closures |
| `POST /sms-changes` | Manual SMS reportable change |
| `GET /dashboard` | Compliance summary |
| `GET /audit-export?format=pdf` | One-click audit PDF pack |
| `POST /rtw-verify-share-code` | eVisa share code verification (IDSP or dev mock) |
| `GET /reporting-triggers` | Open Home Office reporting tasks |

### Grievance (`/grievance`)

Requires `ENCRYPTION_KEY`. Uses `disciplinary.read` / `disciplinary.write` permissions.

| Endpoint | Description |
|----------|-------------|
| `POST /cases` | Open case with ACAS deadlines |
| `POST /cases/{id}/notes` | Add encrypted investigation note |
| `POST /cases/{id}/suspend-employee` | Suspend + trigger compliance alert |
| `POST /cases/{id}/close` | Close case; dismissal/resignation starts offboarding |

### Offboarding (`/offboarding`)

| Endpoint | Description |
|----------|-------------|
| `POST /workflows` | Start leaver workflow |
| `POST /workflows/{id}/cessation-reported` | Mark sponsorship cessation submitted |

### HR templates (`/hr-templates`)

Platform templates live in `backend_stub/modules/hr_templates/catalog.py`. When UK law or guidance changes, bump `version`, `change_summary`, and `content_markdown`, then sync:

```bash
python scripts/sync_hr_templates.py
```

`scripts/run_platform_jobs.py` also runs this sync on each cron cycle so tenants always receive legal updates without manual steps.

| Endpoint | Description |
|----------|-------------|
| `GET /hr-templates` | List templates with platform version, sync status, pending updates |
| `GET /hr-templates/updates` | Templates where a newer platform version is available |
| `GET /hr-templates/{id}` | Effective content + revision history |
| `GET /hr-templates/{id}/revisions` | Published version history |
| `PUT /hr-templates/{id}` | Save tenant-customised template (pins `based_on_platform_version`) |
| `POST /hr-templates/{id}/apply-platform-update` | Replace custom copy with latest platform text |
| `POST /hr-templates/{id}/reset` | Remove tenant override (always uses platform latest) |
| `GET /hr-templates/{id}/download?variant=platform\|effective` | Versioned Markdown download (filename includes version) |
| `POST /hr-templates/sync-platform` | Master admin: push catalog to database |

Seed library: `python scripts/seed_hr_templates.py` (fresh installs run this automatically).

### AI assistant (`/ai`)

Uses **Google Gemini 2.0 Flash** by default (cheapest practical option for HR drafting). Set `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey).

| Endpoint | Description |
|----------|-------------|
| `GET /ai/status` | Provider configured + tenant enabled |
| `PATCH /ai/settings` | Enable/disable AI for tenant |
| `POST /ai/draft-document` | Generate or refine HR document markdown |

Requires `AI_ENABLED=1` globally and tenant toggle in admin.

### Events (`/events`)

| Endpoint | Description |
|----------|-------------|
| `POST /subscriptions` | Register webhook for domain events |
| `POST /process-pending` | Admin: replay unprocessed events |

Event types: `employee.status_changed`, `grievance.opened`, `grievance.closed`, `offboarding.started`.

## 8. Local login

After seeding tenant `1`:

| Portal | Customer ID | Username | Password |
|--------|-------------|----------|----------|
| Tenant HR | `1` | `hr@shiftswifthr.co.uk` | `ShiftswiftHR-Tenant-2026` |
| Master admin | `999` | `admin@shiftswifthr.co.uk` | `ShiftswiftHR-Platform-2026` |

- URL: `POST /auth/tenant-login`
- Body: `{"username":"hr@shiftswifthr.co.uk","password":"ShiftswiftHR-Tenant-2026","tenant_id":"1"}`
- Header on all tenant calls: `X-Tenant-Id: 1`

Re-seed or run `python scripts/seed_app_users.py` to remove legacy `demo` / `admin` / `hr` accounts.

## 9. Production checklist

- [ ] Strong `JWT_SECRET` (32+ characters)
- [ ] `ENCRYPTION_KEY` stored in secrets manager
- [ ] `RTW_STORAGE_DIR` on encrypted volume with backups
- [ ] Cron job for `run_platform_jobs.py` (includes HR template catalog sync)
- [ ] Notification delivery worker (SMTP/SMS) for `notifications` table
- [ ] Stripe webhook endpoint configured
- [ ] HTTPS + `FORCE_HTTPS=1`
- [ ] Solicitor review of EULA (`docs/eula_hr_module.md`)

## 10. Future integrations

| Integration | Status |
|-------------|--------|
| IDSP digital RTW (TrustID/Yoti/Credas) | Planned — env `IDSP_API_KEY` |
| PDF audit pack export | JSON export live; PDF wrapper planned |
| Attendance system → absence days | Use `POST /absence-days` or build connector |

For module-specific backlog items see `docs/sponsor_licence_backlog.md`.
