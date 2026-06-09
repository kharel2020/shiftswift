"""ShiftSwift HR API — modular backend layout and client setup."""

# ShiftSwift HR Backend

Python **FastAPI** API for UK hospitality HR: employees, Home Office compliance, grievance cases, offboarding, billing, and contracts.

## Directory layout

```
backend_stub/
├── main.py                 # App entry — registers all module routers
├── brand.py                # Domain, URLs, @shiftswifthr.co.uk emails
├── config.py               # Environment settings
├── deps.py                 # Auth dependencies (JWT, tenant header)
├── rbac.py                 # Role permissions matrix
│
├── core/                   # Shared infrastructure
│   ├── database.py         # PostgreSQL connection
│   ├── events.py           # Domain event outbox + processing
│   ├── crypto.py           # AES-256-GCM for grievance notes
│   └── permissions.py      # RBAC checks for routes
│
├── modules/                # Business domains (one folder per area)
│   ├── registry.py         # Module catalog for /setup/modules
│   ├── employees/          # Core workforce + sponsor profile sync
│   ├── compliance/         # Audit export, expiry jobs
│   ├── grievance/          # Case management + encrypted notes
│   ├── offboarding/        # ACAS + sponsorship cessation
│   └── events/             # Webhook subscriptions + listeners
│
├── admin_routes.py         # Admin workspace (profile, employees, docs)
├── compliance_routes.py    # Home Office sponsor licence API
├── billing_routes.py       # Stripe B2B billing
├── contracts_routes.py     # Legal contract pack
├── signup_routes.py        # Tenant signup
├── sponsor_licence_compliance.py  # Compliance business logic
└── auth_service.py           # Login + JWT
```

## Quick start (local fresh install)

From the repository root:

```bash
bash scripts/fresh_install.sh
bash scripts/start_local.sh
```

Production domain: **shiftswifthr.co.uk** (`app.`, `api.`, `www.` subdomains).

Brand and email defaults live in `brand.py` and `backend_stub/.env.example`.

Verify: `GET http://localhost:3000/setup/brand`, `/setup/modules`, `/health`.

## Client setup checklist

| Step | Action |
|------|--------|
| 1 | Run all SQL migrations in order (`001` → `028`) |
| 2 | Set `DATABASE_URL`, `JWT_SECRET` (32+ chars in production) |
| 3 | Set `ENCRYPTION_KEY` (64 hex chars) for grievance module |
| 4 | Create `RTW_STORAGE_DIR` path with write access |
| 5 | Schedule `scripts/run_platform_jobs.py` daily (cron) |
| 6 | Configure Stripe vars if billing is enabled |
| 7 | Point frontend `apiBaseUrl` to your API |

Verify: `GET http://localhost:3000/setup/modules` and `GET /health`.

## Module map

| Module | Prefix | Purpose |
|--------|--------|---------|
| Auth | `/auth` | Login, refresh, verify |
| Employees | `/admin/employees` | Core employee CRUD |
| Compliance | `/compliance/sponsor-licence` | RTW, absence, SMS, audit export |
| Grievance | `/grievance` | Cases, encrypted notes, suspend trigger |
| Offboarding | `/offboarding` | Leaver workflows, cessation reports |
| Events | `/events` | Webhooks + domain event processing |
| Billing | `/billing` | Plans, Stripe, promo codes |
| Contracts | `/contracts` | MSA/DPA generation |
| Admin | `/admin` | Tenant settings, documents |

## Cross-module events

When employee status changes, grievance closes, or offboarding starts, the **domain event bus** (`core/events.py`) runs listeners in `modules/events/listeners.py`:

- **Suspended sponsored worker** → `sponsor_reporting_triggers` + compliance notification
- **Grievance with absence context** → compliance monitoring alert
- **Grievance closed (dismissal/resignation)** → offboarding workflow + ACAS appeal deadline
- **Offboarding (sponsored)** → sponsorship cessation reporting trigger

Register outbound webhooks: `POST /events/subscriptions`.

## Background jobs

```bash
# Daily — absence day-9, SMS status refresh, visa/RTW expiry, pending events
python scripts/run_platform_jobs.py
```

Legacy script still works: `scripts/run_sponsor_compliance_jobs.py`.

Deliver notifications only: `python scripts/deliver_notifications.py`

## Documentation

Full client guide: [`docs/backend_setup_guide.md`](../docs/backend_setup_guide.md)

Architecture backlog: [`docs/sponsor_licence_backlog.md`](../docs/sponsor_licence_backlog.md)
