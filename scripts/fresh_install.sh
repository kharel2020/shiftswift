#!/usr/bin/env bash
# Drop database, apply all migrations from scratch, seed, and write .env — no upgrade path.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

DB_NAME="${DB_NAME:-shiftswift_hr}"
DB_USER="${DB_USER:-$(whoami)}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DATABASE_URL="${DATABASE_URL:-postgresql://${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}}"

PSQL="${PSQL:-psql}"
CREATEDB="${CREATEDB:-createdb}"
DROPDB="${DROPDB:-dropdb}"
if command -v brew >/dev/null 2>&1; then
  for BREW_PG in /opt/homebrew/opt/postgresql@16/bin /usr/local/opt/postgresql@16/bin; do
    [ -x "${BREW_PG}/psql" ] && PSQL="${BREW_PG}/psql"
    [ -x "${BREW_PG}/createdb" ] && CREATEDB="${BREW_PG}/createdb"
    [ -x "${BREW_PG}/dropdb" ] && DROPDB="${BREW_PG}/dropdb"
  done
fi

echo "==> ShiftSwift HR fresh install (shiftswifthr.co.uk)"
echo "    WARNING: This drops database '${DB_NAME}' and rebuilds from scratch."
echo "    Database URL: ${DATABASE_URL}"

echo "==> Dropping existing database (if any)"
"${DROPDB}" -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" --if-exists "${DB_NAME}" 2>/dev/null || true

echo "==> Creating empty database"
"${CREATEDB}" -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" "${DB_NAME}"

echo "==> Python virtualenv"
PYTHON="${PYTHON:-python3.11}"
if ! command -v "${PYTHON}" >/dev/null 2>&1; then
  PYTHON=python3
fi
"${PYTHON}" -m venv backend_stub/.venv
source backend_stub/.venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r backend_stub/requirements.txt

echo "==> Applying migrations (clean schema)"
DATABASE_URL="${DATABASE_URL}" bash scripts/run_migrations.sh

JWT_SECRET="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"

ENCRYPTION_KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"

cat > backend_stub/.env <<EOF
APP_ENV=development
APP_DOMAIN=shiftswifthr.co.uk
MARKETING_URL=https://www.shiftswifthr.co.uk
APP_URL=https://app.shiftswifthr.co.uk
API_URL=https://api.shiftswifthr.co.uk
LOCAL_API_URL=http://localhost:3000
LOCAL_APP_URL=http://localhost:5173
DATABASE_URL=${DATABASE_URL}
JWT_SECRET=${JWT_SECRET}
JWT_ACCESS_MINUTES=60
JWT_REFRESH_DAYS=7
MASTER_CUSTOMER_ID=999
CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://app.shiftswifthr.co.uk,https://www.shiftswifthr.co.uk
TRUSTED_HOSTS=localhost,127.0.0.1,api.shiftswifthr.co.uk,app.shiftswifthr.co.uk,www.shiftswifthr.co.uk
FORCE_HTTPS=0
USE_DB=1
LOGIN_RATE_LIMIT=10
LOGIN_RATE_WINDOW_SECONDS=900
MAX_UPLOAD_BYTES=10485760
ENCRYPTION_KEY=${ENCRYPTION_KEY}
RTW_STORAGE_DIR=uploads/rtw_immutable
EMAIL_HELLO=hello@shiftswifthr.co.uk
EMAIL_SUPPORT=support@shiftswifthr.co.uk
EMAIL_LEGAL=legal@shiftswifthr.co.uk
EMAIL_NOREPLY=noreply@shiftswifthr.co.uk
EMAIL_COMPLIANCE=compliance@shiftswifthr.co.uk
EMAIL_ADMIN=admin@shiftswifthr.co.uk
EMAIL_HR=hr@shiftswifthr.co.uk
PROVIDER_LEGAL_NAME="Datasoftware Analytics Ltd"
PROVIDER_COMPANY_NUMBER="14568900"
PROVIDER_EMAIL=legal@shiftswifthr.co.uk
PROVIDER_ADDRESS="235 Charlbury Road, Nottingham, NG8 1NF"
SMTP_FROM=noreply@shiftswifthr.co.uk
COMPLIANCE_ALERT_EMAIL=compliance@shiftswifthr.co.uk
AI_ENABLED=1
AI_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
AI_MAX_OUTPUT_TOKENS=4096
EOF

cat > .env <<EOF
DATABASE_URL=${DATABASE_URL}
APP_DOMAIN=shiftswifthr.co.uk
EOF

echo "==> Seeding users, billing catalog, contracts, tenant branding, HR templates"
python3 scripts/seed_app_users.py
python3 scripts/seed_billing_catalog.py
python3 scripts/seed_contract_templates.py
python3 scripts/seed_tenant_branding.py
python3 scripts/seed_hr_templates.py
python3 scripts/seed_time_punch.py

chmod +x scripts/start_local.sh scripts/run_migrations.sh scripts/install_local.sh scripts/security_audit.sh scripts/generate_secrets.sh scripts/seed_time_punch.py

echo ""
echo "Fresh install complete."
echo ""
echo "  Domain:  shiftswifthr.co.uk"
echo "  App:     bash scripts/start_local.sh"
echo "  Login:   http://localhost:5173/business-login.html"
echo "  API:     http://localhost:3000/health"
echo "  Tenant:  Customer ID 1 · hr@shiftswifthr.co.uk"
echo "  Master:  Customer ID 999 · admin@shiftswifthr.co.uk"
echo "  Passwords: see README.md (local dev only)"
echo ""
