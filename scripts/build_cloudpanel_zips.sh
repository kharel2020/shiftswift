#!/usr/bin/env bash
# Build CloudPanel upload zips: API package + frontend package.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/deploy/cloudpanel/dist"
STAGE="${ROOT_DIR}/.pack-staging"
rm -rf "${STAGE}" "${OUT_DIR}"
mkdir -p "${OUT_DIR}" "${STAGE}/api" "${STAGE}/frontend"

echo "==> Staging API package"
rsync -a \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude 'uploads' \
  --exclude 'storage/contracts' \
  "${ROOT_DIR}/backend_stub/" "${STAGE}/api/backend_stub/"
rsync -a "${ROOT_DIR}/migrations/" "${STAGE}/api/migrations/"
rsync -a "${ROOT_DIR}/scripts/run_migrations.sh" \
  "${ROOT_DIR}/scripts/seed_app_users.py" \
  "${ROOT_DIR}/scripts/seed_billing_catalog.py" \
  "${ROOT_DIR}/scripts/seed_contract_templates.py" \
  "${ROOT_DIR}/scripts/seed_tenant_branding.py" \
  "${ROOT_DIR}/scripts/seed_hr_templates.py" \
  "${ROOT_DIR}/scripts/seed_time_punch.py" \
  "${STAGE}/api/scripts/"
cp "${ROOT_DIR}/deploy/cloudpanel/install-api.sh" "${STAGE}/api/install-api.sh"
cp "${ROOT_DIR}/deploy/cloudpanel/INSTALL-API.md" "${STAGE}/api/INSTALL-API.md"
cp "${ROOT_DIR}/backend_stub/.env.production.example" "${STAGE}/api/backend_stub/.env.production.example" 2>/dev/null || true
chmod +x "${STAGE}/api/install-api.sh" "${STAGE}/api/scripts/run_migrations.sh"

echo "==> Staging frontend package"
rsync -a \
  --exclude '.DS_Store' \
  "${ROOT_DIR}/frontend/" "${STAGE}/frontend/"
cp "${ROOT_DIR}/deploy/cloudpanel/INSTALL-FRONTEND.md" "${STAGE}/frontend/INSTALL-FRONTEND.md"

echo "==> Creating zips"
(
  cd "${STAGE}/api"
  zip -r "${OUT_DIR}/shiftswifthr-api.zip" . -x "*.DS_Store"
)
(
  cd "${STAGE}/frontend"
  zip -r "${OUT_DIR}/shiftswifthr-frontend.zip" . -x "*.DS_Store"
)

rm -rf "${STAGE}"

echo ""
echo "Built:"
echo "  ${OUT_DIR}/shiftswifthr-api.zip"
echo "  ${OUT_DIR}/shiftswifthr-frontend.zip"
ls -lh "${OUT_DIR}/"*.zip
