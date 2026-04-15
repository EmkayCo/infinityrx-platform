#!/usr/bin/env bash
# Run every reference-data loader against the database matching INFINITYRX_ENV.
#
# Usage: ./infrastructure/scripts/run_reference_loaders.sh [dev|mock|prod]
#
# Each loader gets a per-script timeout. Failures are logged but do not abort
# the run — we want to know how much of the reference catalog made it in,
# even if some upstream sources are unreachable.

set -eo pipefail

ENV_NAME="${1:-dev}"
REPO_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"
cd "$REPO_ROOT"

case "$ENV_NAME" in
  dev)  ENV_FILE=".env.dev"  ;;
  mock) ENV_FILE=".env.mock" ;;
  prod) ENV_FILE=".env.prod" ;;
  *)    echo "Usage: $0 [dev|mock|prod]" >&2; exit 2 ;;
esac
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE"; exit 2; }

if [ "$ENV_NAME" = "prod" ] && [ -z "${PROD_DB_PASSWORD:-}" ]; then
  echo "ERROR: prod loaders require PROD_DB_PASSWORD exported in shell" >&2
  exit 2
fi

export INFINITYRX_ENV="$ENV_NAME"
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# Loaders use create_engine(DATABASE_URL_SYNC) — strip the +asyncpg / +psycopg2
# prefix entirely and let SQLAlchemy default to psycopg2.
SYNC_URL="${DATABASE_URL_SYNC/+asyncpg/}"
SYNC_URL="${SYNC_URL/+psycopg2/}"
export DATABASE_URL_SYNC="$SYNC_URL"
export DATABASE_URL="$SYNC_URL"

LOG_DIR="var/loader-logs/$ENV_NAME"
mkdir -p "$LOG_DIR"

# (script, args, timeout_seconds, description)
LOADERS=(
  "load_oig_leie.py|--no-flag||OIG LEIE exclusions"
  "load_ncpdp.py|||NCPDP pharmacies (local zip)"
  "load_fda_ndc.py|||FDA NDC drugs"
  "load_orange_book.py|||FDA Orange Book"
  "load_cms_asp.py|||CMS ASP pricing"
  "load_cms_nadac.py|||CMS NADAC pricing"
  "load_nppes.py|--sample||NPPES (sample mode)"
  "load_new_sources.py|rxnorm||RxNorm concepts"
  "load_new_sources.py|fda_rems||FDA REMS"
  "load_new_sources.py|fda_purple_book||FDA Purple Book"
  "load_new_sources.py|fda_drug_shortages||FDA Drug Shortages"
  "load_new_sources.py|medicare_opt_out||Medicare Opt-Out"
)

declare -a RESULTS

echo "════════════════════════════════════════════════════════════"
echo "  Reference loaders: $ENV_NAME"
echo "  DATABASE_URL_SYNC: ${DATABASE_URL_SYNC%@*}@***"
echo "  Logs              : $LOG_DIR/"
echo "════════════════════════════════════════════════════════════"

for entry in "${LOADERS[@]}"; do
  IFS='|' read -r script arg timeout desc <<<"$entry"
  : "${timeout:=600}"
  log="$LOG_DIR/${script%.py}.log"
  echo
  echo "── $desc ──"
  echo "scripts/$script $arg → $log"
  start=$(date +%s)
  if [ "$arg" = "--no-flag" ] || [ -z "$arg" ]; then
    args_array=()
  else
    args_array=("$arg")
  fi
  # macOS has no /usr/bin/timeout; use perl-alarm wrapper if available, else
  # fall back to running unbounded and trust the loaders to terminate.
  set +e
  if command -v perl >/dev/null 2>&1; then
    perl -e 'alarm shift @ARGV; exec @ARGV' "$timeout" \
      "$REPO_ROOT/.venv/bin/python" "scripts/$script" "${args_array[@]}" \
      >"$log" 2>&1
  else
    "$REPO_ROOT/.venv/bin/python" "scripts/$script" "${args_array[@]}" >"$log" 2>&1
  fi
  rc=$?
  set -e
  elapsed=$(( $(date +%s) - start ))
  if [ $rc -eq 0 ]; then
    echo "  ✓ OK  (${elapsed}s)"
    RESULTS+=("OK   ${elapsed}s  $script $arg  $desc")
  elif [ $rc -eq 124 ]; then
    echo "  ⏱  TIMEOUT after ${timeout}s"
    RESULTS+=("TIME ${timeout}s  $script $arg  $desc")
  else
    echo "  ✗ FAIL rc=$rc (${elapsed}s) — see $log"
    tail -5 "$log" | sed 's/^/    | /'
    RESULTS+=("FAIL ${elapsed}s  $script $arg  $desc  rc=$rc")
  fi
done

echo
echo "════════════════════════════════════════════════════════════"
echo "  Summary"
echo "════════════════════════════════════════════════════════════"
for r in "${RESULTS[@]}"; do
  echo "  $r"
done
