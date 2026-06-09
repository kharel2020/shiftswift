#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

: "${DATABASE_URL:?DATABASE_URL is required}"

python3 scripts/run_sponsor_compliance_jobs.py
