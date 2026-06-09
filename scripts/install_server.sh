#!/usr/bin/env bash
# Production server install — run on Ubuntu/Debian VPS as deploy user with sudo.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

APP_USER="${APP_USER:-shiftswift}"
APP_ROOT="${APP_ROOT:-/opt/shiftswifthr}"
DOMAIN="${APP_DOMAIN:-shiftswifthr.co.uk}"
DB_NAME="${DB_NAME:-shiftswift_hr}"
DB_USER="${DB_USER:-shiftswift}"
API_PORT="${API_PORT:-8000}"

echo "==> ShiftSwift HR server install"
echo "    App root: ${APP_ROOT}"
echo "    Domain:   ${DOMAIN}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash scripts/install_server.sh"
  exit 1
fi

echo "==> System packages"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  python3 python3-venv python3-pip postgresql postgresql-contrib \
  nginx certbot python3-certbot-nginx rsync curl

echo "==> App user and directories"
id -u "${APP_USER}" >/dev/null 2>&1 || useradd --system --create-home --home-dir "${APP_ROOT}" --shell /bin/bash "${APP_USER}"
install -d -o "${APP_USER}" -g "${APP_USER}" \
  "${APP_ROOT}" \
  "${APP_ROOT}/uploads/rtw_immutable" \
  /var/log/shiftswift-hr

echo "==> Sync application"
rsync -a --delete \
  --exclude backend_stub/.venv \
  --exclude .git \
  --exclude node_modules \
  "${ROOT_DIR}/" "${APP_ROOT}/"

echo "==> Python environment"
sudo -u "${APP_USER}" bash -lc "
  cd '${APP_ROOT}/backend_stub'
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
"

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
  DB_PASS="$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)"
  sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"
  sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
  echo "Database password (save securely): ${DB_PASS}"
else
  echo "Database user ${DB_USER} already exists — skipping create."
  DB_PASS="CHANGE_ME"
fi

if [ ! -f "${APP_ROOT}/backend_stub/.env" ]; then
  JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  ENCRYPTION_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  cat > "${APP_ROOT}/backend_stub/.env" <<EOF
APP_ENV=production
APP_DOMAIN=${DOMAIN}
MARKETING_URL=https://www.${DOMAIN}
APP_URL=https://app.${DOMAIN}
API_URL=https://api.${DOMAIN}
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}
JWT_SECRET=${JWT_SECRET}
JWT_ACCESS_MINUTES=60
JWT_REFRESH_DAYS=7
MASTER_CUSTOMER_ID=999
CORS_ALLOW_ORIGINS=https://app.${DOMAIN},https://www.${DOMAIN}
TRUSTED_HOSTS=localhost,127.0.0.1,api.${DOMAIN},app.${DOMAIN},www.${DOMAIN}
FORCE_HTTPS=1
USE_DB=1
LOGIN_RATE_LIMIT=10
LOGIN_RATE_WINDOW_SECONDS=900
MAX_UPLOAD_BYTES=10485760
ENCRYPTION_KEY=${ENCRYPTION_KEY}
RTW_STORAGE_DIR=${APP_ROOT}/uploads/rtw_immutable
EMAIL_ADMIN=admin@${DOMAIN}
EMAIL_HR=hr@${DOMAIN}
EMAIL_EMPLOYEE=employee@${DOMAIN}
PROVIDER_LEGAL_NAME="Datasoftware Analytics Ltd"
PROVIDER_COMPANY_NUMBER="14568900"
PROVIDER_EMAIL=legal@${DOMAIN}
PROVIDER_ADDRESS="235 Charlbury Road, Nottingham, NG8 1NF"
SMTP_FROM=noreply@${DOMAIN}
AI_ENABLED=0
EOF
  chown "${APP_USER}:${APP_USER}" "${APP_ROOT}/backend_stub/.env"
  chmod 600 "${APP_ROOT}/backend_stub/.env"
  echo "Created ${APP_ROOT}/backend_stub/.env — review before going live."
fi

echo "==> Database migrations and seed"
sudo -u "${APP_USER}" bash -lc "
  set -a
  source '${APP_ROOT}/backend_stub/.env'
  set +a
  cd '${APP_ROOT}'
  bash scripts/run_migrations.sh
  python3 scripts/seed_app_users.py
  python3 scripts/seed_billing_catalog.py
  python3 scripts/seed_contract_templates.py
  python3 scripts/seed_tenant_branding.py
  python3 scripts/seed_hr_templates.py
  python3 scripts/seed_time_punch.py
"

echo "==> systemd service"
sed "s|/opt/shiftswifthr|${APP_ROOT}|g; s|8000|${API_PORT}|g" \
  "${APP_ROOT}/deploy/shiftswift-api.service" > /etc/systemd/system/shiftswift-api.service
systemctl daemon-reload
systemctl enable shiftswift-api
systemctl restart shiftswift-api

echo "==> nginx site"
sed "s|shiftswifthr.co.uk|${DOMAIN}|g; s|/opt/shiftswifthr|${APP_ROOT}|g; s|8000|${API_PORT}|g" \
  "${APP_ROOT}/deploy/nginx-shiftswift.conf" > "/etc/nginx/sites-available/shiftswift"
ln -sf /etc/nginx/sites-available/shiftswift /etc/nginx/sites-enabled/shiftswift
nginx -t
systemctl reload nginx

echo ""
echo "Server install complete."
echo "  1. Point DNS: www, app, api -> this server"
echo "  2. TLS: certbot --nginx -d www.${DOMAIN} -d app.${DOMAIN} -d api.${DOMAIN}"
echo "  3. Change seeded passwords: python3 scripts/seed_app_users.py (with DEV_* env vars)"
echo "  4. Health: curl -s https://api.${DOMAIN}/health"
echo ""
echo "See docs/server_installation.md for full checklist."
