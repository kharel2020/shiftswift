# Server installation — ShiftSwift HR

Step-by-step guide for **staging** or **production** on Ubuntu/Debian VPS.

**Domains (production):**

| Host | Purpose |
|------|---------|
| `www.shiftswifthr.co.uk` | Marketing |
| `app.shiftswifthr.co.uk` | Admin + employee portal (static frontend) |
| `api.shiftswifthr.co.uk` | FastAPI backend |

---

## Prerequisites

- Ubuntu 22.04+ or Debian 12+ VPS (2 GB RAM minimum recommended)
- Root or sudo access
- DNS A records for `www`, `app`, and `api` pointing to the server IP
- Repo copied to the server (git clone or rsync from your machine)

---

## 1. Automated install

From the repo root on the server:

```bash
sudo APP_DOMAIN=shiftswifthr.co.uk bash scripts/install_server.sh
```

This script:

1. Installs Python 3, PostgreSQL, nginx, certbot
2. Creates system user `shiftswift` and app root `/opt/shiftswifthr`
3. Creates venv and installs Python dependencies
4. Creates Postgres database `shiftswift_hr` (prints password on first run)
5. Writes `backend_stub/.env` with production defaults (if missing)
6. Runs migrations and seed scripts
7. Installs systemd service and nginx site

**Files installed:**

- `deploy/shiftswift-api.service` → `/etc/systemd/system/shiftswift-api.service`
- `deploy/nginx-shiftswift.conf` → `/etc/nginx/sites-available/shiftswift`

---

## 2. TLS (Let's Encrypt)

After DNS has propagated:

```bash
sudo certbot --nginx \
  -d www.shiftswifthr.co.uk \
  -d app.shiftswifthr.co.uk \
  -d api.shiftswifthr.co.uk
```

Certbot updates nginx for HTTPS. Confirm:

```bash
curl -s https://api.shiftswifthr.co.uk/health
# {"status":"ok","app":"ShiftSwift HR","environment":"production"}
```

---

## 3. Post-install configuration

### 3.1 Review environment

Edit `/opt/shiftswifthr/backend_stub/.env`:

```bash
sudo -u shiftswift nano /opt/shiftswifthr/backend_stub/.env
```

Confirm:

- `APP_ENV=production`
- `FORCE_HTTPS=1`
- `JWT_SECRET` is long and unique (≥ 32 characters)
- `ENCRYPTION_KEY` is set (64 hex characters)
- `CORS_ALLOW_ORIGINS` lists only `https://` origins
- `STRIPE_*` keys if billing is enabled
- `SMTP_*` if email alerts are required
- `AI_ENABLED=0` unless `GEMINI_API_KEY` is configured

Restart API after changes:

```bash
sudo systemctl restart shiftswift-api
```

### 3.2 Change default passwords

Seeded dev accounts must not remain in production:

```bash
sudo -u shiftswift bash -lc '
  cd /opt/shiftswifthr
  source backend_stub/.env
  export DEV_MASTER_PASSWORD="your-strong-master-password"
  export DEV_TENANT_PASSWORD="your-strong-hr-password"
  export DEV_EMPLOYEE_PASSWORD="your-strong-employee-password"
  python3 scripts/seed_app_users.py
'
```

Or create real users via HR admin after first login.

### 3.3 Optional demo time punch data

```bash
sudo -u shiftswift bash -lc '
  cd /opt/shiftswifthr
  source backend_stub/.env
  python3 scripts/seed_time_punch.py
'
```

---

## 4. Staging vs production

Use a **separate VPS** or separate database for staging:

| Setting | Staging | Production |
|---------|---------|------------|
| `APP_DOMAIN` | `staging.shiftswifthr.co.uk` or subdomain | `shiftswifthr.co.uk` |
| Stripe | Test keys | Live keys |
| Database | `shiftswift_hr_staging` | `shiftswift_hr` |
| Backups | Optional | Required daily |

Install on staging first; run the [production readiness checklist](./production_readiness.md) before promoting to production.

---

## 5. Operations

### Service management

```bash
sudo systemctl status shiftswift-api
sudo systemctl restart shiftswift-api
sudo journalctl -u shiftswift-api -f
tail -f /var/log/shiftswift-hr/api.log
```

### Apply new migrations after deploy

```bash
sudo -u shiftswift bash -lc '
  cd /opt/shiftswifthr
  source backend_stub/.env
  bash scripts/run_migrations.sh
'
sudo systemctl restart shiftswift-api
```

### Deploy updated code

```bash
sudo rsync -a --delete \
  --exclude backend_stub/.venv \
  --exclude .git \
  /path/to/local/shiftswifthr/ /opt/shiftswifthr/

sudo -u shiftswift bash -lc '
  cd /opt/shiftswifthr/backend_stub
  source .venv/bin/activate
  pip install -r requirements.txt
'
sudo systemctl restart shiftswift-api
```

### Backups (example — adjust paths)

```bash
sudo -u postgres pg_dump shiftswift_hr | gzip > /var/backups/shiftswift_hr_$(date +%F).sql.gz
sudo tar czf /var/backups/shiftswift_uploads_$(date +%F).tar.gz /opt/shiftswifthr/uploads
```

Schedule with cron. **Test restore** monthly.

### Security audit

```bash
cd /opt/shiftswifthr && bash scripts/security_audit.sh
```

---

## 6. Troubleshooting

| Symptom | Check |
|---------|--------|
| 502 from api subdomain | `systemctl status shiftswift-api`; logs in `/var/log/shiftswift-hr/` |
| Login 500 | Migration `034_auth_mfa.sql` applied? `DATABASE_URL` correct? |
| CORS errors | `CORS_ALLOW_ORIGINS` includes exact frontend origin (`https://app...`) |
| App won't start in prod | Weak `JWT_SECRET` — run `bash scripts/generate_secrets.sh` |
| Time punch fails | `035_time_punch.sql` applied; employee email matches `employees.email` |

---

## 7. Checklist after install

- [ ] `https://api.shiftswifthr.co.uk/health` returns OK
- [ ] `https://app.shiftswifthr.co.uk/business-login.html` loads
- [ ] HR can sign in and open admin console
- [ ] Employee can sign in and see time clock
- [ ] Default passwords changed
- [ ] Backups scheduled
- [ ] Uptime monitor on `/health`
- [ ] [production_readiness.md](./production_readiness.md) reviewed
