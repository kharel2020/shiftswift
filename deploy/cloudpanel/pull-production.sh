#!/usr/bin/env bash
# Pull latest shiftswift from GitHub and deploy API + frontend on CloudPanel.
# Run on the server as a user that can restart shiftswifthr-api (sudo once if needed).
set -euo pipefail

REPO_URL="${SHIFTSWIFT_REPO_URL:-https://github.com/kharel2020/shiftswift.git}"
API_ROOT="${SHIFTSWIFT_API_ROOT:-/home/shiftswifthr-api/htdocs/api.shiftswifthr.co.uk}"
APP_ROOT="${SHIFTSWIFT_APP_ROOT:-/home/shiftswifthr-app/htdocs/app.shiftswifthr.co.uk}"
WWW_ROOT="${SHIFTSWIFT_WWW_ROOT:-/home/shiftswifthr/htdocs/www.shiftswifthr.co.uk}"
SERVICE="${SHIFTSWIFT_SERVICE:-shiftswifthr-api}"

echo "==> ShiftSwift HR production pull"
echo "    API:  ${API_ROOT}"
echo "    App:  ${APP_ROOT}"
echo "    WWW:  ${WWW_ROOT}"

if [ ! -d "${API_ROOT}/.git" ]; then
  echo "No git repo at ${API_ROOT}. First-time setup:"
  echo "  cd ${API_ROOT} && git clone ${REPO_URL} ."
  exit 1
fi

cd "${API_ROOT}"
echo "==> git pull"
git pull --ff-only

if [ -f backend_stub/.venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source backend_stub/.venv/bin/activate
  echo "==> pip install"
  pip install -q -r backend_stub/requirements.txt
else
  echo "==> venv missing — run deploy/cloudpanel/install-api.sh first"
  exit 1
fi

if [ -f backend_stub/.env ]; then
  set -a
  # shellcheck disable=SC1091
  source backend_stub/.env
  set +a
  echo "==> migrations"
  bash scripts/run_migrations.sh
else
  echo "WARNING: backend_stub/.env missing — skipped migrations"
fi

if command -v systemctl >/dev/null 2>&1; then
  echo "==> restart ${SERVICE}"
  sudo systemctl restart "${SERVICE}"
else
  echo "WARNING: systemctl not found — restart API manually"
fi

echo "==> sync frontend"
rsync -a --delete "${API_ROOT}/frontend/" "${APP_ROOT}/"
rsync -a --delete "${API_ROOT}/frontend/" "${WWW_ROOT}/"

echo "==> health check"
if command -v curl >/dev/null 2>&1; then
  curl -sf "https://api.shiftswifthr.co.uk/health" && echo "" || echo "Health check failed (API may still be starting)"
fi

echo "Done."
