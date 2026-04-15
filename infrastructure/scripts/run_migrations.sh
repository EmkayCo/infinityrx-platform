#!/usr/bin/env bash
# Run Alembic migrations for every module against one of the three databases.
#
# Usage: ./infrastructure/scripts/run_migrations.sh [dev|mock|prod]
#
# We pass DATABASE_URL/DATABASE_URL_SYNC inline so they take precedence over
# .env.local, which Settings still loads via env_file. .env.{dev,mock,prod}
# is the source of truth for everything else.

set -euo pipefail

ENV_NAME="${1:-dev}"
REPO_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"
cd "$REPO_ROOT"

case "$ENV_NAME" in
  dev)  ENV_FILE=".env.dev"  ;;
  mock) ENV_FILE=".env.mock" ;;
  prod) ENV_FILE=".env.prod" ;;
  *)    echo "Usage: $0 [dev|mock|prod]" >&2; exit 2 ;;
esac

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE" >&2
  exit 2
fi

# Source the env file into this script only (don't pollute the caller).
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# Force DATABASE_URL_SYNC to use asyncpg too — modules/core-platform/alembic
# wraps it in async_engine_from_config, so the psycopg2 prefix breaks.
export DATABASE_URL_SYNC="$DATABASE_URL"

# RabbitMQ host bootstrap: every module loads Settings even if it doesn't
# touch the queue, and Settings needs RABBITMQ_URL to be set.
: "${RABBITMQ_URL:?RABBITMQ_URL not set in $ENV_FILE}"

MODULES=(
  "core-platform"
  "drug-database"
  "pharmacy-directory"
  "prescriber-directory"
)

echo "════════════════════════════════════════════════════════════"
echo "  Migrations: $ENV_NAME"
echo "  DATABASE_URL: ${DATABASE_URL%@*}@***"
echo "════════════════════════════════════════════════════════════"

for module in "${MODULES[@]}"; do
  module_dir="$REPO_ROOT/modules/$module"
  ini="$module_dir/alembic.ini"
  if [ ! -f "$ini" ]; then
    echo "Skipping $module — no alembic.ini"
    continue
  fi
  echo
  echo "── $module ──"
  # Each module's env.py has different cwd assumptions (some use
  # `prepend_sys_path = .`, some compute paths from __file__). Running from
  # inside the module dir is the only thing that works for all of them.
  # Use the root .venv directly — `uv run` from a module dir tries to create
  # its own per-dir env and can't find alembic since modules don't ship
  # individual pyproject.toml files.
  #
  # prescriber-directory's env.py uses sync engine_from_config(), so it needs
  # a sync driver URL (psycopg2). All other modules use async_engine.
  if [ "$module" = "prescriber-directory" ]; then
    SYNC_URL="${DATABASE_URL/+asyncpg/+psycopg2}"
    ( cd "$module_dir" && \
      DATABASE_URL="$SYNC_URL" \
      DATABASE_URL_SYNC="$SYNC_URL" \
      "$REPO_ROOT/.venv/bin/alembic" upgrade head ) || {
      echo "FAILED: $module"; exit 1
    }
  else
    ( cd "$module_dir" && "$REPO_ROOT/.venv/bin/alembic" upgrade head ) || {
      echo "FAILED: $module"; exit 1
    }
  fi
done

echo
echo "✅ All migrations applied to $ENV_NAME"
