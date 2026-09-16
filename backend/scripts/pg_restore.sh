#!/usr/bin/env bash
# ==========================================================
# pg_restore.sh — restore an Alquiler PostgreSQL dump.
# ==========================================================
# Restores a dump produced by pg_backup.sh into a PostgreSQL database,
# covering BOTH cases:
#
#   1. Fresh/empty target database — restored directly.
#   2. Existing target database  — `--reset` drops and recreates the
#      `public` schema first, giving a clean restore.
#
# Usage:
#   ./backend/scripts/pg_restore.sh                          # latest dump in backend/backups/
#   ./backend/scripts/pg_restore.sh /path/alquiler_2026-01-15.sql
#   ./backend/scripts/pg_restore.sh --reset /path/dump.sql   # reset an existing DB first
#
# Options:
#   --reset    Drop and recreate the `public` schema before restoring
#              (destroys ALL data in the target database).
#   --createdb Create the database if it does not exist.
#   --verbose  Stream psql output.
#
# Requires PostgreSQL client tools (psql/createdb) and DB_* settings from
# backend/.env unless overridden in the environment.
# ==========================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "${SCRIPT_DIR}")"
ENV_FILE="${BACKEND_DIR}/.env"

RESET=0
CREATEDB=0
VERBOSE=0
INPUT=""
for arg in "$@"; do
  case "${arg}" in
    --reset)    RESET=1 ;;
    --createdb) CREATEDB=1 ;;
    --verbose)  VERBOSE=1 ;;
    --help|-h)
      echo "Usage: $0 [--reset] [--createdb] [--verbose] [DUMP.sql]"
      echo "If DUMP.sql is omitted, the newest file in backend/backups/ is used."
      exit 0 ;;
    -*) echo "Unknown option: ${arg}" >&2; exit 2 ;;
    *) INPUT="${arg}" ;;
  esac
done

# ------------------------------------------------------------------
# Load DB_* settings (same safe reader as pg_backup.sh).
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

DB_NAME="${DB_NAME:-${POSTGRES_DB:-alquiler}}"
DB_USER="${DB_USER:-${POSTGRES_USER:-alquiler}}"
export PGPASSWORD="${DB_PASSWORD:-${POSTGRES_PASSWORD:-}}"

PSQL=(psql --set=ON_ERROR_STOP=1 --quiet)
CREATEDB_CMD=(createdb)
[ -n "${DB_HOST:-}" ] && PSQL+=(--host "${DB_HOST}") && CREATEDB_CMD+=(--host "${DB_HOST}")
[ -n "${DB_PORT:-}" ] && PSQL+=(--port "${DB_PORT}") && CREATEDB_CMD+=(--port "${DB_PORT}")
[ -n "${DB_USER:-}" ] && PSQL+=(--username "${DB_USER}") && CREATEDB_CMD+=(--username "${DB_USER}")

# ------------------------------------------------------------------
# Resolve the dump file to restore.
# ------------------------------------------------------------------
if [ -z "${INPUT}" ]; then
  BACKUP_DIR="${BACKEND_DIR}/backups"
  INPUT="$(ls -1 "${BACKUP_DIR}"/alquiler_*.sql 2>/dev/null | sort | tail -n1 || true)"
fi
if [ -z "${INPUT}" ] || [ ! -f "${INPUT}" ]; then
  echo "ERROR: no dump file given and none found in ${BACKUP_DIR:-backend/backups}." >&2
  exit 1
fi

echo "=== Restoring to database '${DB_NAME}' from: ${INPUT}"

# ------------------------------------------------------------------
# Ensure the target database exists (optional).
# ------------------------------------------------------------------
if [ "${CREATEDB}" = "1" ]; then
  if "${PSQL[@]}" --dbname="postgres" -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1; then
    echo "Database '${DB_NAME}' already exists."
  else
    if ! "${CREATEDB_CMD[@]}" "${DB_NAME}" >/dev/null 2>&1; then
      echo "ERROR: could not create database '${DB_NAME}'. Check permissions." >&2
      exit 1
    fi
    echo "Created database '${DB_NAME}'."
  fi
fi

# ------------------------------------------------------------------
# Optional hard reset of an existing database.
# ------------------------------------------------------------------
if [ "${RESET}" = "1" ]; then
  echo "!!! Dropping and recreating the 'public' schema on '${DB_NAME}'. This DELETES all data."
  read -r -p "Type 'yes' to continue: " CONFIRM
  if [ "${CONFIRM}" != "yes" ]; then
    echo "Aborted." >&2
    exit 1
  fi
  "${PSQL[@]}" --dbname="${DB_NAME}" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' >/dev/null
  echo "Schema 'public' reset."
fi

# ------------------------------------------------------------------
# Restore.
# ------------------------------------------------------------------
if [ "${VERBOSE}" = "1" ]; then
  "${PSQL[@]}" --dbname="${DB_NAME}" --file="${INPUT}"
else
  "${PSQL[@]}" --dbname="${DB_NAME}" --file="${INPUT}" >/dev/null
fi

echo "=== Restore complete."
echo "Next steps:"
echo "  1. Set the new host's DATABASE_URL (see DEPLOYMENT.md)."
echo "  2. python manage.py migrate   (no-op if dump already matches migrations; harmless otherwise)"
echo "  3. Verify a few records, e.g. python manage.py shell"
echo
echo "NOTE: the dump restores data only. Environment secrets (SECRET_KEY, DB_*,"
echo "EMAIL_*) always stay in the host's .env — never in the dump."