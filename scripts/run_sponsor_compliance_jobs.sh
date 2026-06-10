#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ -f "${ROOT_DIR}/scripts/load_env.sh" ]; then
  # shellcheck source=scripts/load_env.sh
  source "${ROOT_DIR}/scripts/load_env.sh"
  load_env_file "${ROOT_DIR}/backend_stub/.env" || true
fi

: "${DATABASE_URL:?DATABASE_URL is required — set it in backend_stub/.env}"

PYTHON="${ROOT_DIR}/backend_stub/.venv/bin/python3"
if [ ! -x "${PYTHON}" ]; then
  PYTHON=python3
fi

exec "${PYTHON}" scripts/run_sponsor_compliance_jobs.py
