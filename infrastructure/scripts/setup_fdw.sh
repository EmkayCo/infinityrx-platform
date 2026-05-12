#!/usr/bin/env bash
# setup_fdw.sh — Wave B7 (Phase 11A) FDW configuration.
#
# For each env DB (infinityrx_dev, infinityrx_mock):
#   1. Enable postgres_fdw extension
#   2. Idempotently create FDW server pointing at infinityrx_reference
#   3. Idempotently create user mapping (ifx_<env>_app → ifx_ref_reader)
#   4. Pre-check for cross-source-schema table-name collisions in the
#      reference DB (would conflict on IMPORT INTO single `reference`)
#   5. IMPORT FOREIGN SCHEMA <src> ... INTO reference for each source
#      schema in infinityrx_reference (consolidates `shared`,
#      `drug_database`, `drug_db` into ONE local `reference` namespace
#      per Phase 11A LOCKED line 17, 20: "postgres_fdw → reference.*
#      foreign tables")
#
# Modes:
#   (default)  Idempotent setup — safe to re-run; no destructive ops
#   --refresh  Same as default but only IMPORTs newly-added source tables
#              (FDW drift mitigation; uses LIMIT TO clause)
#   --reset    DESTRUCTIVE — DROP SERVER ... CASCADE then recreate.
#              Requires INFINITYRX_DESTRUCTIVE_OK=1 env var to proceed.
#   --dry-run  Print intended SQL; do not execute
#   --env dev|mock|both  Target one or both env DBs (default: both)

set -euo pipefail

# Source the shared psql strict helpers (provides psql_strict + docker_psql_strict)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/lib/psql_strict.sh"

# Local-dev mode flag: route SQL through `docker compose exec -T postgres psql`
# instead of host `psql` (host may not have the client installed).
IN_DOCKER=${IN_DOCKER:-1}

# Container-aware psql wrapper (supports superuser + per-env app roles).
# Connects via Postgres unix socket inside the container, so DATABASE_URL
# auth doesn't apply — just `-U <role> -d <db>`.
exec_psql_strict() {
  local user="$1" db="$2" sql="$3"
  if [ "$IN_DOCKER" = "1" ]; then
    docker_psql_strict "$user" "$db" "$sql"
  else
    psql_strict "postgresql://$user@localhost:5432/$db" "$sql"
  fi
}

exec_psql_run() {
  local user="$1" db="$2" sql="$3"
  if [ "$DRY_RUN" = "1" ]; then
    echo "DRY-RUN [$user@$db]: ${sql:0:300}..."
  elif [ "$IN_DOCKER" = "1" ]; then
    # </dev/null prevents docker compose exec -T from consuming the
    # caller's stdin — without it, a `while IFS= read; done <<< "$X"`
    # loop wrapping this call exits after the first iteration because
    # docker exec slurped the rest of the heredoc.
    docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$user" -d "$db" -c "$sql" </dev/null >/dev/null
  else
    psql -v ON_ERROR_STOP=1 "postgresql://$user@localhost:5432/$db" -c "$sql" >/dev/null
  fi
}

MODE="default"
TARGET_ENV="both"
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --refresh) MODE="refresh"; shift ;;
    --reset)   MODE="reset"; shift ;;
    --verify)  MODE="verify"; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --env)     TARGET_ENV="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ "$MODE" = "reset" ] && [ "${INFINITYRX_DESTRUCTIVE_OK:-0}" != "1" ]; then
  echo "ERROR: --reset is destructive (DROP SERVER ... CASCADE drops foreign tables)." >&2
  echo "Set INFINITYRX_DESTRUCTIVE_OK=1 to acknowledge per .claude/rules/destructive-actions.md" >&2
  exit 2
fi

case "$TARGET_ENV" in
  dev)  ENVS=(dev) ;;
  mock) ENVS=(mock) ;;
  both) ENVS=(dev mock) ;;
  *) echo "Unknown --env value: $TARGET_ENV (need dev|mock|both)" >&2; exit 2 ;;
esac

# ── --verify mode ─────────────────────────────────────────────────────────────
# Iterates every entry in expected_reference_tables.txt and confirms each
# foreign table is queryable via FDW in each target env DB.
# Foreign tables are mounted as reference.<table> regardless of source schema.
# PASS = query exits 0 (empty result is fine — FDW link is the contract).
# Uses exec_psql_strict (respects IN_DOCKER flag, same as Phase 1 path).
# Exit 0 if all tables pass; exit 1 if any fail.
#
# B9.A C11: manifest-derived count (replaces hard-coded `expected 66`).
# As B9.B-G grow the manifest 66 → 264, the verify step grows with it —
# no edit to this script required. The MIN_MANIFEST_COUNT floor catches
# accidental truncation; the deterministic sort ensures stable output
# ordering for diff-based gate evidence.
MIN_MANIFEST_COUNT=66
if [ "$MODE" = "verify" ]; then
  LIB_DIR="$SCRIPT_DIR/lib"
  MANIFEST="$LIB_DIR/expected_reference_tables.txt"
  if [ ! -f "$MANIFEST" ]; then
    echo "FATAL: manifest not found: $MANIFEST" >&2
    exit 2
  fi

  # Build a deterministic sorted view of manifest entries (C11):
  # strip CR, drop blanks + comments, then sort lexicographically by
  # schema|table so the iteration order is reproducible across runs
  # and across operators with different filesystem behavior.
  MANIFEST_SORTED="$(
    awk '
      { sub(/\r$/, "") }
      /^[[:space:]]*$/ { next }
      /^[[:space:]]*#/ { next }
      { print }
    ' "$MANIFEST" | sort
  )"

  MANIFEST_COUNT=$(printf '%s\n' "$MANIFEST_SORTED" | grep -c .)
  # Floor — manifest must not shrink below the B7 baseline. As B9.B-G
  # land new tiers (179 → 245 → 261 → 262 → 264) operators can bump
  # this floor in the same commit that grows the manifest; the value
  # below is the B7-shipped baseline.
  if [ "$MANIFEST_COUNT" -lt "$MIN_MANIFEST_COUNT" ]; then
    echo "FATAL: manifest has ${MANIFEST_COUNT} data lines; below floor of ${MIN_MANIFEST_COUNT}. Manifest must not shrink — investigate before proceeding." >&2
    exit 2
  fi
  echo "  Manifest: ${MANIFEST_COUNT} entries (floor: ${MIN_MANIFEST_COUNT})"

  total_pass=0
  total_fail=0
  fail_details=()

  for env in "${ENVS[@]}"; do
    env_db="infinityrx_${env}"
    env_pass=0
    env_fail=0
    echo "── Verifying FDW foreign tables in ${env_db} ──"
    # B9.A C11: iterate the deterministic-sorted manifest view so output
    # ordering is reproducible across runs / operators / filesystems.
    while IFS='|' read -r schema table; do
      # Already stripped of blanks/comments by the awk pass above.
      [[ -z "$schema" || -z "$table" ]] && continue
      sql="SELECT 1 FROM reference.${table} LIMIT 1"
      # exec_psql_strict respects IN_DOCKER flag (docker compose exec -T or
      # host psql depending on IN_DOCKER setting), consistent with Phase 1 path.
      if exec_psql_strict "infinityrx" "${env_db}" "${sql}" >/dev/null 2>&1; then
        env_pass=$((env_pass + 1))
      else
        echo "  FAIL: ${env_db} :: reference.${table} (source schema: ${schema})" >&2
        fail_details+=("${env_db}::reference.${table}")
        env_fail=$((env_fail + 1))
      fi
    done <<< "$MANIFEST_SORTED"
    echo "  ${env_db}: ${env_pass} PASS, ${env_fail} FAIL"
    total_pass=$((total_pass + env_pass))
    total_fail=$((total_fail + env_fail))
  done

  echo
  echo "════════════════════════════════════════════════════"
  echo "  setup_fdw.sh --verify complete"
  echo "  Total: ${total_pass} PASS, ${total_fail} FAIL"
  if [ "${#fail_details[@]}" -gt 0 ]; then
    echo "  Failed tables:"
    for item in "${fail_details[@]}"; do
      echo "    - ${item}"
    done
  fi
  echo "════════════════════════════════════════════════════"
  exit $((total_fail > 0 ? 1 : 0))
fi
# ── end --verify ──────────────────────────────────────────────────────────────

# Reference DB connection — must be set in environment
: "${DATABASE_URL_SYNC_REFERENCE:?DATABASE_URL_SYNC_REFERENCE must be set}"

# Pre-check: cross-schema table-name collisions in reference DB.
# Pure-SQL query — no shell array construction (adversarial round 3 fix).
# Tables that exist in multiple schemas legitimately and are NOT
# reference data — exclude them from collision check + IMPORT.
# `alembic_version` is migration bookkeeping (one per module's alembic).
IGNORED_TABLES="('alembic_version','dataq_ingestion_runs','ingestion_schedules')"

# Schemas that exist in reference DB but should NOT be FDW-imported.
# `core` exists because core-platform alembic runs against reference DB
# for shared.ingestion_runs but also creates env-DB-shape tables
# (tenants, users, audit_log) with custom ENUM types. Those types are
# local to the reference DB and don't transfer through FDW. Reference
# data lives in shared / drug_database / drug_db / pharmacy_dir /
# prescriber_dir.
IGNORED_SCHEMAS="('core')"

echo "── Pre-check: cross-source-schema table-name collisions ──"
COLLISIONS=$(exec_psql_strict "ifx_reference_writer" "infinityrx_reference" "
  SELECT table_name || ' (' || string_agg(table_schema, ', ' ORDER BY table_schema) || ')' AS conflict
  FROM information_schema.tables
  WHERE table_schema NOT IN ('pg_catalog','information_schema','public')
    AND table_schema NOT LIKE 'pg_%'
    AND table_type = 'BASE TABLE'
    AND table_name NOT IN $IGNORED_TABLES
  GROUP BY table_name
  HAVING count(DISTINCT table_schema) > 1
  ORDER BY table_name") || exit 1

if [ -n "$COLLISIONS" ]; then
  echo "FATAL: table-name collisions across source schemas — IMPORT INTO reference would conflict:" >&2
  echo "$COLLISIONS" >&2
  echo "Resolution: rename source tables OR import into per-schema local namespaces (deviates from Phase 11A LOCKED)." >&2
  exit 1
fi
echo "  OK — no collisions"
echo

# Enumerate source schemas (one per line) from reference DB
SOURCE_SCHEMAS=$(exec_psql_strict "ifx_reference_writer" "infinityrx_reference" "
  SELECT schema_name FROM information_schema.schemata
  WHERE schema_name NOT IN ('pg_catalog','information_schema','public')
    AND schema_name NOT LIKE 'pg_%'
    AND schema_name NOT IN $IGNORED_SCHEMAS
  ORDER BY schema_name") || exit 1

if [ -z "$SOURCE_SCHEMAS" ]; then
  echo "FATAL: no source schemas found in reference DB; loaders did not create any schema." >&2
  exit 1
fi

for env in "${ENVS[@]}"; do
  echo "── Setting up FDW in infinityrx_${env} ──"
  ENV_DB="infinityrx_${env}"
  # Use superuser for FDW setup — CREATE EXTENSION requires it, and
  # the env app role doesn't have it.
  ENV_USER="infinityrx"

  # Optional --reset: destructive recreate
  if [ "$MODE" = "reset" ]; then
    echo "  --reset: DROP SERVER infinityrx_reference_srv CASCADE"
    exec_psql_run "$ENV_USER" "$ENV_DB" "DROP SERVER IF EXISTS infinityrx_reference_srv CASCADE"
  fi

  # 1. Extension
  exec_psql_run "$ENV_USER" "$ENV_DB" "CREATE EXTENSION IF NOT EXISTS postgres_fdw"

  # 2. Idempotent server (CREATE only if absent).
  # Use the docker service name 'postgres' as the FDW host since the
  # env DB connects to itself on the same cluster — postgres_fdw uses
  # postgres-the-service-name's resolution context inside the container.
  # Locally-running script outside the container would use 'localhost'.
  FDW_HOST="${FDW_HOST:-postgres}"
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_foreign_server WHERE srvname = 'infinityrx_reference_srv') THEN
        CREATE SERVER infinityrx_reference_srv
          FOREIGN DATA WRAPPER postgres_fdw
          OPTIONS (host '$FDW_HOST', port '5432', dbname 'infinityrx_reference');
      END IF;
    END \$\$"

  # 2b. ALTER SERVER for option drift (host/port/dbname)
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    ALTER SERVER infinityrx_reference_srv
      OPTIONS (SET host '$FDW_HOST', SET port '5432', SET dbname 'infinityrx_reference')"

  # 3. Idempotent user mapping for the env's app role (app code's role)
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    CREATE USER MAPPING IF NOT EXISTS FOR ifx_${env}_app
      SERVER infinityrx_reference_srv
      OPTIONS (user 'ifx_ref_reader', password 'ref_password')"
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    ALTER USER MAPPING FOR ifx_${env}_app
      SERVER infinityrx_reference_srv
      OPTIONS (SET user 'ifx_ref_reader', SET password 'ref_password')"

  # 3c. Also create a mapping for the superuser (infinityrx) since
  # IMPORT FOREIGN SCHEMA runs as the connected user, not as the app
  # role. The superuser needs its own mapping so this very script can
  # execute the IMPORT.
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    CREATE USER MAPPING IF NOT EXISTS FOR $ENV_USER
      SERVER infinityrx_reference_srv
      OPTIONS (user 'ifx_ref_reader', password 'ref_password')"
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    ALTER USER MAPPING FOR $ENV_USER
      SERVER infinityrx_reference_srv
      OPTIONS (SET user 'ifx_ref_reader', SET password 'ref_password')"

  # 4. Local landing schema
  exec_psql_run "$ENV_USER" "$ENV_DB" "CREATE SCHEMA IF NOT EXISTS reference"
  exec_psql_run "$ENV_USER" "$ENV_DB" "GRANT USAGE ON SCHEMA reference TO ifx_${env}_app"

  # 5. IMPORT each source schema INTO local `reference`
  while IFS= read -r src_schema; do
    src_schema=${src_schema%$'\r'}
    [ -z "$src_schema" ] && continue
    if ! [[ "$src_schema" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
      echo "FATAL: invalid schema name '$src_schema' — refusing to IMPORT" >&2
      exit 1
    fi
    # Build comma-separated LIMIT TO list of all importable tables
    # (excludes IGNORED_TABLES — migration bookkeeping not reference data).
    IMPORT_TABLES=$(exec_psql_strict "ifx_reference_writer" "infinityrx_reference" "
      SELECT table_name FROM information_schema.tables
      WHERE table_schema = '${src_schema}' AND table_type = 'BASE TABLE'
        AND table_name NOT IN $IGNORED_TABLES
      ORDER BY table_name") || exit 1
    if [ -z "$IMPORT_TABLES" ]; then
      echo "  ${src_schema}: no importable tables (all excluded)"
      continue
    fi

    if [ "$MODE" = "refresh" ]; then
      # Diff: source tables - already-imported foreign tables
      NEW_TABLES=$(exec_psql_strict "$ENV_USER" "$ENV_DB" "
        WITH src AS (
          SELECT '${src_schema}' AS s, unnest(string_to_array('$(echo "$IMPORT_TABLES" | tr '\n' ',' | sed 's/,$//')', ',')) AS table_name
        ),
        existing AS (
          SELECT ftrelid::regclass::text AS qual_name FROM pg_foreign_table
        )
        SELECT s.table_name FROM src s
        WHERE 'reference.' || s.table_name NOT IN (SELECT qual_name FROM existing)") || exit 1
      if [ -z "$NEW_TABLES" ]; then
        echo "  ${src_schema}: no new tables to import"
        continue
      fi
      LIMIT_LIST=$(echo "$NEW_TABLES" | paste -sd, -)
    else
      LIMIT_LIST=$(echo "$IMPORT_TABLES" | paste -sd, -)
    fi
    # Use bash parameter expansion (no pipe) to avoid SIGPIPE under
    # `set -o pipefail` — head/cut exiting early would propagate as
    # script failure and break the loop after the first schema.
    LIMIT_PREVIEW="${LIMIT_LIST:0:100}"
    echo "  Importing from ${src_schema} (${LIMIT_PREVIEW}...)"
    exec_psql_run "$ENV_USER" "$ENV_DB" "
      IMPORT FOREIGN SCHEMA ${src_schema} LIMIT TO (${LIMIT_LIST})
        FROM SERVER infinityrx_reference_srv INTO reference"
  done <<< "$SOURCE_SCHEMAS"

  # 6. Grant SELECT on all imported foreign tables to the env app role.
  # IMPORT FOREIGN SCHEMA creates tables owned by the connecting superuser;
  # the app role needs explicit SELECT grants to query them.
  # GRANT USAGE on the schema (step 4) is not sufficient.
  exec_psql_run "$ENV_USER" "$ENV_DB" "GRANT SELECT ON ALL TABLES IN SCHEMA reference TO ifx_${env}_app"

  echo "  OK — FDW configured in infinityrx_${env}"
  echo
done

echo "════════════════════════════════════════════════════"
echo "  setup_fdw.sh complete (mode=$MODE, dry_run=$DRY_RUN)"
echo "════════════════════════════════════════════════════"
