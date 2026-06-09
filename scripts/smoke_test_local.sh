#!/usr/bin/env bash
# Smoke-test API health and login endpoints (starts a temporary API if port 3000 is free).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}/backend_stub"

source .venv/bin/activate
set -a
[ -f .env ] && source .env
set +a

API_PORT="${BACKEND_PORT:-3000}"
BASE="http://127.0.0.1:${API_PORT}"
STARTED_API=0
API_PID=""

cleanup() {
  if [ "${STARTED_API}" = "1" ] && [ -n "${API_PID}" ]; then
    kill "${API_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if ! curl -sf "${BASE}/health" >/dev/null 2>&1; then
  echo "Starting temporary API on ${BASE}..."
  uvicorn main:app --host 127.0.0.1 --port "${API_PORT}" >/tmp/shiftswift-smoke-api.log 2>&1 &
  API_PID=$!
  STARTED_API=1
  for _ in $(seq 1 20); do
    curl -sf "${BASE}/health" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

echo -n "Health: "
curl -sf "${BASE}/health" | head -c 120
echo ""

HR=$(curl -sf -X POST "${BASE}/auth/business-login" \
  -H "Content-Type: application/json" \
  -d '{"username":"hr@shiftswifthr.co.uk","password":"ShiftswiftHR-Tenant-2026"}' || echo FAIL)
if echo "${HR}" | grep -q access_token; then
  echo "Business HR login: OK"
else
  echo "Business HR login: FAILED"
  echo "${HR}" | head -c 300
  exit 1
fi

EMP=$(curl -sf -X POST "${BASE}/auth/employee-login" \
  -H "Content-Type: application/json" \
  -d '{"username":"employee@shiftswifthr.co.uk","password":"ShiftswiftHR-Employee-2026"}' || echo FAIL)
if echo "${EMP}" | grep -q access_token; then
  echo "Employee login: OK"
else
  echo "Employee login: FAILED"
  echo "${EMP}" | head -c 300
  exit 1
fi

MASTER=$(curl -sf -X POST "${BASE}/auth/master-login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@shiftswifthr.co.uk","password":"ShiftswiftHR-Platform-2026"}' || echo FAIL)
if echo "${MASTER}" | grep -q access_token; then
  echo "Master login: OK"
else
  echo "Master login: FAILED"
  echo "${MASTER}" | head -c 300
  exit 1
fi

echo "Smoke test passed."
