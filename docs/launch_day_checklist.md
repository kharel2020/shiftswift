# ShiftSwift HR — launch day checklist

**Use this on launch day.** Tick each box. One operator name + date at the bottom.

**Production URLs**

| Service | URL |
|---------|-----|
| Marketing | https://www.shiftswifthr.co.uk |
| App | https://app.shiftswifthr.co.uk |
| API health | https://api.shiftswifthr.co.uk/health |

**Server (CloudPanel)**

| Item | Path |
|------|------|
| API + repo | `/home/shiftswifthr-api/htdocs/api.shiftswifthr.co.uk` |
| App frontend | `/home/shiftswifthr-app/htdocs/app.shiftswifthr.co.uk` |
| Marketing www | `/home/shiftswifthr/htdocs/www.shiftswifthr.co.uk` |

---

## A. Deploy (do first if not already done today)

- [ ] `cd /home/shiftswifthr-api/htdocs/api.shiftswifthr.co.uk && git pull --ff-only`
- [ ] `bash scripts/run_migrations.sh` (through **055** employee GDPR consent)
- [ ] `sudo systemctl restart shiftswifthr-api`
- [ ] Rsync frontend → app + www (or `bash deploy/cloudpanel/pull-production.sh`)
- [ ] `curl -s https://api.shiftswifthr.co.uk/health` → `"status":"ok"`, `"environment":"production"`
- [ ] GDPR deploy verify:
  - [ ] `curl -s "https://api.shiftswifthr.co.uk/auth/reset-password/context?token=invalid"` → invalid/expired message (**not** 404)
  - [ ] `curl -s https://app.shiftswifthr.co.uk/password-reset.js | grep reset-password/context` → match found

---

## B. Security & environment

- [ ] `APP_ENV=production` in `backend_stub/.env`
- [ ] `JWT_SECRET` ≥ 32 characters (not a dev default)
- [ ] `ENCRYPTION_KEY` set (64 hex chars — grievance notes)
- [ ] `FORCE_HTTPS=1`
- [ ] `CORS_ALLOW_ORIGINS` — `https://` only (app + www)
- [ ] `TRUSTED_HOSTS` includes www, app, api domains
- [ ] `chmod 600 backend_stub/.env`
- [ ] Dev/demo passwords rotated or removed on production
- [ ] `bash scripts/security_audit.sh` run once post-deploy

---

## C. Backups & jobs

- [ ] Manual backup run succeeds:
  ```bash
  cd /home/shiftswifthr-api/htdocs/api.shiftswifthr.co.uk
  source scripts/load_env.sh && load_env_file backend_stub/.env
  bash scripts/backup_production.sh
  ```
- [ ] Backup files exist under `/var/backups/shiftswifthr/YYYY-MM-DD/`
- [ ] Daily backup cron configured for `shiftswifthr` user
- [ ] **Restore test** completed at least once (logged with date)
- [ ] Cron for `scripts/run_platform_jobs.py` (portal reminders, trials, template sync)
- [ ] Cron for `scripts/run_sponsor_compliance_jobs.sh` (if using sponsor features)
- [ ] Uptime monitor on `https://api.shiftswifthr.co.uk/health`

---

## D. Legal pages live

- [ ] https://www.shiftswifthr.co.uk/privacy-policy.html
- [ ] https://www.shiftswifthr.co.uk/cookies.html
- [ ] https://www.shiftswifthr.co.uk/eula.html
- [ ] https://www.shiftswifthr.co.uk/dpa.html
- [ ] https://www.shiftswifthr.co.uk/payment-terms.html
- [ ] Cookie banner works on www (accept + essential-only paths)

---

## E. 15-minute product smoke test (production)

Use a **real trial tenant** or pilot business — not demo passwords.

| # | Test | Pass |
|---|------|------|
| 1 | Business HR login (+ MFA if enabled) | ☐ |
| 2 | HR → Employees → send/resend **portal invite** | ☐ |
| 3 | Employee opens invite link → sees **employer GDPR notice** + checkbox | ☐ |
| 4 | Employee sets password → login opens **Employee** tab | ☐ |
| 5 | Employee portal loads (documents / overview) | ☐ |
| 6 | Time punch from phone (if customer will use it) | ☐ |
| 7 | HR → upload document → employee can download | ☐ |
| 8 | Self-service signup → legal checkboxes required → trial starts | ☐ |
| 9 | Welcome + getting-started emails received (check spam) | ☐ |
| 10 | Forgot password → reset link works (HR and Employee tabs) | ☐ |

---

## F. Billing (only if charging on launch day)

- [ ] Stripe **live** keys in `.env` (not test)
- [ ] Webhook endpoint registered + `STRIPE_WEBHOOK_SECRET` set
- [ ] One live checkout completes
- [ ] Subscription / plan status updates in HR admin
- [ ] Direct Debit path tested (if offered)

---

## G. Customer onboarding (tell every new business)

- [ ] Customer signed **MSA + DPA** (or your signing process started)
- [ ] Customer told: **they are the data controller** for employee data
- [ ] Customer told: they need their own **employee privacy notice** (mention HR system + Time Clock GPS if used)
- [ ] Customer knows: sign in on **Employee** tab for staff portal (not Business HR)
- [ ] Customer knows: portal invite emails may land in **junk** — use Resend in Employees panel

---

## H. Organisational (not code — confirm before scale)

- [ ] ICO registration current
- [ ] Breach notification owner assigned (`legal@datasoftwareanalytics.co.uk`)
- [ ] SAR / erasure process documented
- [ ] Support inbox monitored: **support@shiftswifthr.co.uk**
- [ ] PI / cyber insurance (recommended)

---

## I. Launch decision

**Soft launch (pilot customer)** — ready when **A + B + C + D + E** are ticked.

**Paid launch / marketing spend** — also tick **F + G + H**.

| Decision | Tick one |
|----------|----------|
| Go — soft launch with pilot customer | ☐ |
| Go — open to paying customers | ☐ |
| No-go — blockers listed below | ☐ |

**Blockers (if any):**

```
1.
2.
3.
```

---

## Sign-off

| Field | Value |
|-------|-------|
| Operator | |
| Date | |
| Pilot / first customer name | |
| Notes | |

---

*Related: [production_go_live_checklist.md](./production_go_live_checklist.md) · [production_readiness.md](./production_readiness.md) · [compliance_checklist.md](./compliance_checklist.md)*
