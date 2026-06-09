# Cyber Essentials readiness — ShiftSwift HR

This document maps **Cyber Essentials** controls to what is implemented in software vs what your **small team** must still do organisationally before certification.

## Target certification

**Cyber Essentials (basic)** — appropriate for selling HR software to private restaurants, cafés, and pubs.

---

## 1. Firewalls and internet gateways

| Control | Software | Your team |
|---------|----------|-----------|
| Boundary firewall | Deploy API/frontend behind nginx/Caddy + cloud firewall | Configure hosting firewall; block admin ports from public internet |
| Default deny | `TRUSTED_HOSTS` in production | Restrict SSH/RDP to known IPs |

---

## 2. Secure configuration

| Control | Status | Notes |
|---------|--------|-------|
| Remove default credentials | **Patched** | Demo users seeded with bcrypt; change before production |
| Disable dev API docs in prod | **Patched** | `/docs` hidden when `APP_ENV=production` |
| Security headers | **Patched** | `X-Frame-Options`, `nosniff`, HSTS when `FORCE_HTTPS=1` |
| HTTPS only | **Config ready** | Set `FORCE_HTTPS=1` + TLS certificate on reverse proxy |
| Least-privilege API roles | **Patched** | HR/admin roles required for compliance mutations |

**Production setup:**
```bash
bash scripts/generate_secrets.sh
# Copy backend_stub/.env.production.example → backend_stub/.env
# Set APP_ENV=production, DATABASE_URL, CORS_ALLOW_ORIGINS (https://...)
bash scripts/run_migrations.sh
python3 scripts/seed_app_users.py   # then change passwords
bash scripts/security_audit.sh
```

---

## 3. Security update management

| Control | Software | Your team |
|---------|----------|-----------|
| Dependency patching | `scripts/security_audit.sh` runs `pip audit` | Run monthly; patch OS within 14 days (CE requirement) |
| Pin dependencies | `backend_stub/requirements.txt` | Review and upgrade quarterly |

---

## 4. User access control

| Control | Status | Implementation |
|---------|--------|----------------|
| Password hashing | **Done** | bcrypt via `passlib` (`app_users.password_hash`) |
| Session tokens | **Done** | JWT access (60 min) + refresh (7 days) |
| Brute-force protection | **Done** | 10 attempts / 15 min per IP+username |
| Tenant isolation | **Done** | JWT tenant must match `X-Tenant-Id` (except admin) |
| Audit trail | **Done** | `security_audit_events` table |
| MFA | **Done (in-app TOTP)** | Also enable MFA on business email + cloud admin (CE organisational control) |

---

## 5. Malware protection

Not applicable inside application code. **Install antivirus on all staff laptops** and keep it updated (CE requirement).

---

## API security patches included

- `backend_stub/auth_service.py` — bcrypt, JWT, rate limiting, audit logging
- `backend_stub/deps.py` — bearer auth + tenant checks
- `backend_stub/security_middleware.py` — security headers, HTTPS redirect
- `backend_stub/config.py` — production secret validation
- `migrations/022_security_users_audit.sql` — users + audit tables
- `compliance_routes.py` — auth on all sensitive routes; PDF validation

---

## Pre-certification checklist

### Software (this repo)
- [x] Bcrypt password storage
- [x] JWT validation on protected routes
- [x] Login rate limiting
- [x] Security headers
- [x] Production env validation
- [x] Upload size/type validation
- [ ] Deploy behind HTTPS reverse proxy (nginx/Caddy)
- [ ] Replace local dev passwords (`DEV_*` in `.env`) before production
- [ ] UK GDPR privacy notice published on website

### Organisation (your team)
- [ ] MFA on Microsoft 365 / Google Workspace admin accounts
- [ ] Firewall on office/router or cloud VPC
- [ ] Antivirus on all devices
- [ ] OS patches within 14 days
- [ ] Backup policy + tested restore
- [ ] Access list: who has production DB/server access

---

## IASME self-assessment tips

When completing the Cyber Essentials questionnaire:
- State that **application passwords are bcrypt-hashed** and **API uses JWT + HTTPS**.
- Confirm **MFA on email** (not necessarily inside ShiftSwift HR login unless you add it later).
- Host the app on a provider with **firewall controls** (AWS, Azure, DigitalOcean, etc.).

---

## Optional next steps (not required for basic CE)

- MFA inside ShiftSwift HR login (TOTP)
- Cyber Essentials Plus (external vulnerability scan)
- Automated dependency scanning in CI
