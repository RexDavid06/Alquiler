#!/usr/bin/env bash
# ==========================================================
# pg_backup.sh — authoritative PostgreSQL backup for Alquiler.
# ==========================================================
# Produces a timestamped plain-SQL dump:
#
#   backend/backups/alquiler_YYYY-MM-DD.sql
#
# This is the AUTHORITATIVE migration mechanism (see DEPLOYMENT.md).
# The backup must NEVER be committed to Git — backend/backups/ is
# gitignored on purpose.
#
# A plain-SQL dump is chosen because it is trivially inspectable,
# portable across PostgreSQL versions, and restore-friendly on both
# fresh and existing databases.
#
# Usage:
#   ./backend/scripts/pg_backup.sh                     # uses backend/.env DB_*
#   DB_HOST=db.example ./backend/scripts/pg_backup.sh  # override any setting
#   ./backend/scripts/pg_backup.sh /path/custom.sql    # explicit output path
#
# Options:
#   --verbose   Stream pg_dump stderr so progress is visible.
# ==========================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "${SCRIPT_DIR}")"
ENV_FILE="${BACKEND_DIR}/.env"

VERBOSE=0
CUSTOM_OUTPUT=""
for arg in "$@"; do
  case "${arg}" in
    --verbose) VERBOSE=1 ;;
    -*) echo "Unknown option: ${arg}" >&2; echo "Usage: $0 [--verbose] [OUTPUT.sql]" >&2; exit 2 ;;
    *) CUSTOM_OUTPUT="${arg}" ;;
  esac
done

# ------------------------------------------------------------------
# Load DB_* settings from backend/.env unless already in the environment.
# Values are read line-by-line (no source evaluation) so that special
# characters in unrelated .env values can never break the script.
# ------------------------------------------------------------------
load_db_env() {
  for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT DB_SSLMODE POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
    if [ -n "${!key:-}" ]; then
      continue
    fi
    if [ -f "${ENV_FILE}" ]; then
      val="$(grep -E "^${key}=" "${ENV_FILE}" | head -n1 | cut -d= -f2- || true)"
      if [ -n "${val}" ]; then
        export "${key}=${val}"
      fi
    fi
  done
}

load_db_env

# docker-compose.yml overrides DB_HOST to point at the container; for a
# standalone dump, the operator is expected to pass DB_HOST explicitly.
DB_NAME="${DB_NAME:-${POSTGRES_DB:-alquiler}}"
DB_USER="${DB_USER:-${POSTGRES_USER:-alquiler}}"
export PGPASSWORD="${DB_PASSWORD:-${POSTGRES_PASSWORD:-}}"

OUTPUT="${CUSTOM_OUTPUT:-}"
if [ -z "${OUTPUT}" ]; then
  mkdir -p "${BACKEND_DIR}/backups"
  OUTPUT="${BACKEND_DIR}/backups/alquiler_$(date +%F).sql"
fi

mkdir -p "$(dirname "${OUTPUT}")"

PGDUMP="${PGDUMP:-pg_dump}"
ARGS=(--no-owner --no-privileges --format=plain)
[ -n "${DB_HOST:-}" ] && ARGS+=(--host "${DB_HOST}")
[ -n "${DB_PORT:-}" ] && ARGS+=(--port "${DB_PORT}")
[ -n "${DB_USER:-}" ] && ARGS+=(--username "${DB_USER}")

if [ "${VERBOSE}" = "1" ]; then
  "${PGDUMP}" "${ARGS[@]}" --dbname "${DB_NAME}" > "${OUTPUT}"
else
  "${PGDUMP}" "${ARGS[@]}" --dbname "${DB_NAME}" > "${OUTPUT}" 2>/dev/null
fi

if [ ! -s "${OUTPUT}" ]; then
  echo "ERROR: pg_dump produced an empty file." >&2
  exit 1
fi

echo "Database '${DB_NAME}' backed up to: ${OUTPUT}"
echo "This file is gitignored — keep it somewhere safe (do NOT commit)."