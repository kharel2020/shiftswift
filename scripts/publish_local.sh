#!/usr/bin/env bash
# Apply pending migrations, seed users, and smoke-test the local stack.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ ! -d backend_stub/.venv ]; then
  echo "Run bash scripts/fresh_install.sh first."
  exit 1
fi

source backend_stub/.venv/bin/activate
set -a
[ -f backend_stub/.env ] && source backend_stub/.env
set +a

: "${DATABASE_URL:?DATABASE_URL is required in backend_stub/.env}"

echo "==> Applying database migrations"
bash scripts/run_migrations.sh

echo "==> Seeding users and catalog data"
python3 scripts/seed_app_users.py
python3 scripts/sync_hr_templates.py 2>/dev/null || python3 scripts/seed_hr_templates.py

echo "==> Smoke test (starts temporary API if needed)"
bash scripts/smoke_test_local.sh

echo ""
echo "Publish ready. Start the app:"
echo "  bash scripts/start_local.sh"
echo ""
echo "  Business login: http://localhost:5173/business-login.html"
echo "  API health:     http://localhost:3000/health"
