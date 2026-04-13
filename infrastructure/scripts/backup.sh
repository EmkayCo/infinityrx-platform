#!/usr/bin/env bash
# InfinityRx Postgres backup — HIPAA §164.308(a)(7) contingency plan.
#
# Creates a compressed pg_dump with timestamp filename and enforces
# retention: keeps last 7 daily snapshots + 4 weekly snapshots.
#
# Usage:
#   ./backup.sh
#
# Environment variables (with defaults for local docker-compose):
#   PGHOST       (default: localhost)
#   PGPORT       (default: 5432)
#   PGUSER       (default: infinityrx)
#   PGPASSWORD   (required — provide via .pgpass or env)
#   PGDATABASE   (default: infinityrx)
#   BACKUP_DIR   (default: ./var/backups)
#   DAILY_KEEP   (default: 7)
#   WEEKLY_KEEP  (default: 4)
#
# Exit codes:
#   0  success
#   1  pg_dump failed
#   2  missing required environment
#   3  retention pruning failed
set -euo pipefail

: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGUSER:=infinityrx}"
: "${PGDATABASE:=infinityrx}"
: "${BACKUP_DIR:=./var/backups}"
: "${DAILY_KEEP:=7}"
: "${WEEKLY_KEEP:=4}"

if [[ -z "${PGPASSWORD:-}" ]]; then
    # Fall back to .pgpass if the user has one configured
    if [[ ! -f "${HOME}/.pgpass" ]]; then
        echo "FATAL: PGPASSWORD not set and no ~/.pgpass found" >&2
        exit 2
    fi
fi

mkdir -p "${BACKUP_DIR}/daily" "${BACKUP_DIR}/weekly"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DAILY_FILE="${BACKUP_DIR}/daily/infinityrx-${TIMESTAMP}.sql.gz"

echo "[backup] starting pg_dump → ${DAILY_FILE}"

# Use custom format piped to gzip for restorable dumps with compression.
# --format=plain is required so restore.sh can psql it directly.
export PGPASSWORD="${PGPASSWORD:-}"
if ! pg_dump \
        --host="${PGHOST}" \
        --port="${PGPORT}" \
        --username="${PGUSER}" \
        --dbname="${PGDATABASE}" \
        --format=plain \
        --no-owner \
        --no-privileges \
        --clean \
        --if-exists \
        --quote-all-identifiers \
    | gzip -9 > "${DAILY_FILE}"; then
    echo "[backup] pg_dump FAILED" >&2
    rm -f "${DAILY_FILE}"
    exit 1
fi

SIZE=$(wc -c < "${DAILY_FILE}")
echo "[backup] wrote ${DAILY_FILE} (${SIZE} bytes)"

# On Sundays, also copy the snapshot to the weekly ring.
if [[ "$(date -u +%u)" == "7" ]]; then
    WEEKLY_FILE="${BACKUP_DIR}/weekly/infinityrx-${TIMESTAMP}.sql.gz"
    cp "${DAILY_FILE}" "${WEEKLY_FILE}"
    echo "[backup] promoted to weekly → ${WEEKLY_FILE}"
fi

# Retention — keep N most-recent in each ring, delete the rest.
prune() {
    local dir="$1"
    local keep="$2"
    local count
    count=$(find "${dir}" -maxdepth 1 -name 'infinityrx-*.sql.gz' 2>/dev/null | wc -l | tr -d ' ')
    if (( count > keep )); then
        # shellcheck disable=SC2012 — ls is sufficient here; filenames are ISO-sortable
        ls -1t "${dir}"/infinityrx-*.sql.gz | tail -n +$((keep + 1)) | while read -r old; do
            rm -f "${old}"
            echo "[backup] pruned ${old}"
        done
    fi
}

if ! prune "${BACKUP_DIR}/daily" "${DAILY_KEEP}"; then
    echo "[backup] daily retention pruning failed" >&2
    exit 3
fi
if ! prune "${BACKUP_DIR}/weekly" "${WEEKLY_KEEP}"; then
    echo "[backup] weekly retention pruning failed" >&2
    exit 3
fi

echo "[backup] OK"
