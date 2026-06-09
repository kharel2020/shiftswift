#!/usr/bin/env bash
# Local install entry point — runs a full fresh install (drops DB). For upgrades use run_migrations.sh only.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "${ROOT_DIR}/scripts/fresh_install.sh"
