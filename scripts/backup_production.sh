#!/usr/bin/env bash
# Daily production backup — Postgres + RTW PDFs + HR document uploads.
#
# Usage (on API server as root or shiftswifthr):
#   cd /home/shiftswifthr-api/htdocs/api.shiftswifthr.co.uk
#   source scripts/load_env.sh && load_env_file backend_stub/.env
#   bash scripts/backup_production.sh
#
# Cron (08:30 daily, before sponsor compliance jobs at 09:00):
#   30 8 * * * shiftswifthr cd /home/shiftswifthr-api/htdocs/api.shiftswifthr.co.uk && source scripts/load_env.sh && load_env_file backend_stub/.env && bash scripts/backup_production.sh >> /var/log/shiftswifthr/backup.log 2>&1

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

APP_ROOT="${APP_ROOT:-${ROOT_DIR}}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/shiftswifthr}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
DAY="$(date +%F)"
TARGET_DIR="${BACKUP_ROOT}/${DAY}"

if [ -f "${ROOT_DIR}/scripts/load_env.sh" ]; then
  # shellcheck source=scripts/load_env.sh
  source "${ROOT_DIR}/scripts/load_env.sh"
  load_env_file "${ROOT_DIR}/backend_stub/.env" || true
fi

: "${DATABASE_URL:?Set DATABASE_URL in backend_stub/.env}"

RTW_DIR="${RTW_STORAGE_DIR:-${APP_ROOT}/uploads/rtw_immutable}"
DOCS_DIR="${DOCUMENTS_STORAGE_DIR:-${APP_ROOT}/uploads/documents}"

mkdir -p "${TARGET_DIR}"
mkdir -p "$(dirname "${BACKUP_ROOT}")/shiftswifthr" 2>/dev/null || true

echo "==> ShiftSwift HR backup ${STAMP}"
echo "    APP_ROOT=${APP_ROOT}"
echo "    BACKUP_ROOT=${BACKUP_ROOT}"
echo "    RTW_DIR=${RTW_DIR}"
echo "    DOCS_DIR=${DOCS_DIR}"

DB_FILE="${TARGET_DIR}/postgres_${STAMP}.sql.gz"
UPLOADS_FILE="${TARGET_DIR}/uploads_${STAMP}.tar.gz"
MANIFEST="${TARGET_DIR}/manifest_${STAMP}.txt"

{
  echo "backup_stamp=${STAMP}"
  echo "hostname=$(hostname -f 2>/dev/null || hostname)"
  echo "app_root=${APP_ROOT}"
  if command -v git >/dev/null 2>&1 && [ -d "${ROOT_DIR}/.git" ]; then
    echo "git_commit=$(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  fi
  echo "database_url_host=${DATABASE_URL#*@}"
  echo "rtw_dir=${RTW_DIR}"
  echo "documents_dir=${DOCS_DIR}"
} > "${MANIFEST}"

echo "==> Postgres dump"
if command -v pg_dump >/dev/null 2>&1; then
  pg_dump "${DATABASE_URL}" | gzip -9 > "${DB_FILE}"
else
  echo "ERROR: pg_dump not found" >&2
  exit 1
fi

echo "==> Upload directories (RTW + documents)"
if [ -d "${APP_ROOT}/uploads" ]; then
  tar -czf "${UPLOADS_FILE}" -C "${APP_ROOT}" uploads
else
  UPLOAD_PATHS=()
  [ -d "${RTW_DIR}" ] && UPLOAD_PATHS+=("${RTW_DIR}")
  [ -d "${DOCS_DIR}" ] && UPLOAD_PATHS+=("${DOCS_DIR}")
  if [ "${#UPLOAD_PATHS[@]}" -gt 0 ]; then
    tar -czf "${UPLOADS_FILE}" "${UPLOAD_PATHS[@]}"
  else
    echo "WARN: No upload directories found — skipping file archive" | tee -a "${MANIFEST}"
    UPLOADS_FILE=""
  fi
fi

{
  echo "postgres_file=${DB_FILE}"
  echo "uploads_file=${UPLOADS_FILE}"
  echo "postgres_bytes=$(wc -c < "${DB_FILE}" | tr -d ' ')"
  if [ -n "${UPLOADS_FILE}" ] && [ -f "${UPLOADS_FILE}" ]; then
    echo "uploads_bytes=$(wc -c < "${UPLOADS_FILE}" | tr -d ' ')"
  fi
} >> "${MANIFEST}"

chmod 640 "${DB_FILE}" "${MANIFEST}" 2>/dev/null || true
[ -n "${UPLOADS_FILE}" ] && [ -f "${UPLOADS_FILE}" ] && chmod 640 "${UPLOADS_FILE}" 2>/dev/null || true

echo "==> Prune backups older than ${RETENTION_DAYS} days"
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf {} + 2>/dev/null || true

echo "==> Done"
echo "    ${DB_FILE}"
[ -n "${UPLOADS_FILE}" ] && [ -f "${UPLOADS_FILE}" ] && echo "    ${UPLOADS_FILE}"
echo "    ${MANIFEST}"
