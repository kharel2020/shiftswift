#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATIONS_DIR="${ROOT_DIR}/migrations"
ENV_FILE="${ROOT_DIR}/backend_stub/.env"

if [ -z "${DATABASE_URL:-}" ] && [ -f "${ENV_FILE}" ]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/scripts/load_env.sh"
  load_env_file "${ENV_FILE}"
fi

: "${DATABASE_URL:?DATABASE_URL is required — set it in backend_stub/.env or export it}"

PSQL="${PSQL:-psql}"
if ! command -v "${PSQL}" >/dev/null 2>&1; then
  if [ -x /opt/homebrew/opt/postgresql@16/bin/psql ]; then
    PSQL=/opt/homebrew/opt/postgresql@16/bin/psql
  fi
fi

for file in $(ls "${MIGRATIONS_DIR}"/*.sql 2>/dev/null | sort); do
  echo "Applying $(basename "${file}")"
  "${PSQL}" "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "${file}"
done

echo "Migrations complete."
