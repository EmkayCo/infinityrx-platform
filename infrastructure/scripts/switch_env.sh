#!/usr/bin/env bash
# Usage: source infrastructure/scripts/switch_env.sh [prod|dev|mock]
# Loads the matching .env.* file into the current shell.

ENV_NAME="${1:-dev}"

# Resolve repo root (works whether sourced from repo root or any subdir)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]:-$0}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

case "$ENV_NAME" in
  prod)
    ENV_FILE="$REPO_ROOT/.env.prod"
    BANNER="⚠️  PRODUCTION"
    PS_TAG="IFX-PROD"
    ;;
  mock)
    ENV_FILE="$REPO_ROOT/.env.mock"
    BANNER="🎭 MOCK / DEMO"
    PS_TAG="IFX-MOCK"
    ;;
  dev)
    ENV_FILE="$REPO_ROOT/.env.dev"
    BANNER="🔧 DEVELOPMENT"
    PS_TAG="IFX-DEV"
    ;;
  *)
    echo "Unknown environment: $ENV_NAME" >&2
    echo "Usage: source $0 [prod|dev|mock]" >&2
    return 1 2>/dev/null || exit 1
    ;;
esac

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE" >&2
  return 1 2>/dev/null || exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

export IFX_ENV="$ENV_NAME"
export PS1="($PS_TAG) ${PS1:-\\$ }"

echo "$BANNER environment loaded"
echo "  ENVIRONMENT  : $ENVIRONMENT"
echo "  DATABASE_URL : ${DATABASE_URL%@*}@***"
echo "  REDIS_URL    : $REDIS_URL"
echo "  CORS_ORIGINS : $CORS_ORIGINS"
