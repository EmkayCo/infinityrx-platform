#!/usr/bin/env bash
# InfinityRx Postgres restore — companion to backup.sh.
#
# Restores a gzipped pg_dump into a target database. Intended uses:
#   1. Disaster recovery — restore production into a standby instance.
#   2. Restore verification — restore into a throwaway DB and check row
#      counts against the source (automated via verify_backup.py).
#
# Usage:
#   ./restore.sh <backup_file.sql.gz> <target_db_name>
#
# Environment variables (same as backup.sh):
#   PGHOST, PGPORT, PGUSER, PGPASSWORD
#
# The script will DROP AND RECREATE the target database — pass a
# throwaway name (e.g. infinityrx_verify_${TIMESTAMP}) unless you really
# mean to overwrite production.
#
# Exit codes:
#   0  success
#   1  restore failed
#   2  invalid arguments
#   3  source file missing or unreadable
set -euo pipefail

if [[ $# -ne 2 ]]; then
    cat >&2 <<USAGE
Usage: $0 <backup_file.sql.gz> <target_db_name>

  backup_file     path to a gzipped pg_dump produced by backup.sh
  target_db_name  database to (re)create and restore into
USAGE
    exit 2
fi

BACKUP_FILE="$1"
TARGET_DB="$2"

if [[ ! -r "${BACKUP_FILE}" ]]; then
    echo "FATAL: backup file not readable: ${BACKUP_FILE}" >&2
    exit 3
fi

: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGUSER:=infinityrx}"
export PGPASSWORD="${PGPASSWORD:-}"

# Safety: reject targets that look like production.
case "${TARGET_DB}" in
    infinityrx|infinityrx_prod|infinityrx_production)
        echo "FATAL: refusing to restore into '${TARGET_DB}'; use a throwaway name" >&2
        exit 2
        ;;
esac

echo "[restore] target=${TARGET_DB} source=${BACKUP_FILE}"

# Drop + recreate the target DB. The template is postgres (empty, no apps).
# Connect to 'postgres' for admin DDL because we can't DROP the DB we're in.
psql --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" \
     --dbname=postgres --no-psqlrc --quiet --set=ON_ERROR_STOP=1 <<SQL
DROP DATABASE IF EXISTS "${TARGET_DB}";
CREATE DATABASE "${TARGET_DB}" TEMPLATE template0;
SQL

echo "[restore] database re-created, loading dump…"

# Stream the dump through gunzip → psql. ON_ERROR_STOP=1 so any failure
# fails the whole restore (we don't want a half-restored DB to silently
# pass verification).
if ! gunzip -c "${BACKUP_FILE}" \
    | psql --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" \
           --dbname="${TARGET_DB}" --no-psqlrc --quiet --set=ON_ERROR_STOP=1; then
    echo "[restore] FAILED" >&2
    exit 1
fi

echo "[restore] OK — dump restored into ${TARGET_DB}"
