#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ ! -d backend_stub/.venv ]; then
  echo "Run bash scripts/install_local.sh first."
  exit 1
fi

source backend_stub/.venv/bin/activate
set -a
[ -f backend_stub/.env ] && source backend_stub/.env
set +a

BACKEND_PORT="${BACKEND_PORT:-3000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

cleanup() {
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting ShiftSwift HR (shiftswifthr.co.uk) backend on http://127.0.0.1:${BACKEND_PORT}"
(
  cd backend_stub
  uvicorn main:app --host 127.0.0.1 --port "${BACKEND_PORT}" --reload --reload-dir . --reload-exclude '.venv/*'
) &
BACKEND_PID=$!

sleep 2

echo "Starting ShiftSwift HR frontend on http://127.0.0.1:${FRONTEND_PORT}"
(
  cd frontend
  python3 serve_secure.py --port "${FRONTEND_PORT}"
) &
FRONTEND_PID=$!

echo ""
echo "Ready:"
echo "  Website / Admin: http://localhost:${FRONTEND_PORT}"
echo "  Business login:  http://localhost:${FRONTEND_PORT}/business-login.html"
echo "  Admin console:   http://localhost:${FRONTEND_PORT}/admin.html"
echo "  API home:        http://localhost:${BACKEND_PORT}/"
echo "  API login:       http://localhost:${BACKEND_PORT}/app/business-login.html"
echo "  API docs:        http://localhost:${BACKEND_PORT}/docs"
echo "  API health:      http://localhost:${BACKEND_PORT}/health"
echo ""
echo "Press Ctrl+C to stop."

wait
