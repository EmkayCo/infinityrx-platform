#!/usr/bin/env bash
#
# InfinityRx Portal — Local Quality Gate
#
# Runs the 4 checks that must pass before any feature is considered complete:
#   1. TypeScript type check
#   2. ESLint
#   3. Unit tests (vitest)
#   4. Production build
#
# Exits non-zero if any step fails. Use `npm run qa` from the operator root.
# Use `npm run qa:quick` to skip the build step (faster for iteration).
set -euo pipefail

# Color helpers (TTY only — skip in CI where colors are garbled)
if [ -t 1 ]; then
  BOLD=$(printf '\033[1m')
  DIM=$(printf '\033[2m')
  GREEN=$(printf '\033[32m')
  RED=$(printf '\033[31m')
  CYAN=$(printf '\033[36m')
  RESET=$(printf '\033[0m')
else
  BOLD=""; DIM=""; GREEN=""; RED=""; CYAN=""; RESET=""
fi

SKIP_BUILD=${SKIP_BUILD:-0}

step=0
total=4
if [ "$SKIP_BUILD" = "1" ]; then
  total=3
fi

echo "${BOLD}╔══════════════════════════════════════╗${RESET}"
echo "${BOLD}║   InfinityRx Portal Quality Gate     ║${RESET}"
echo "${BOLD}╚══════════════════════════════════════╝${RESET}"

start_time=$(date +%s)

run_step() {
  step=$((step + 1))
  local label="$1"
  local cmd="$2"
  echo
  echo "${CYAN}▸${RESET} ${BOLD}[$step/$total]${RESET} $label..."
  local step_start=$(date +%s)
  if eval "$cmd"; then
    local step_end=$(date +%s)
    local step_elapsed=$((step_end - step_start))
    echo "  ${GREEN}✓${RESET} ${label} (${DIM}${step_elapsed}s${RESET})"
  else
    echo "  ${RED}✗${RESET} ${label} ${RED}FAILED${RESET}"
    exit 1
  fi
}

run_step "TypeScript type check"       "npx tsc --noEmit"
run_step "Lint (eslint)"               "npx eslint app components lib tests --quiet"
run_step "Unit tests (vitest)"         "npx vitest run --reporter=dot"

if [ "$SKIP_BUILD" != "1" ]; then
  run_step "Production build (next)"   "npm run build 2>&1 | tail -12"
fi

elapsed=$(($(date +%s) - start_time))

echo
echo "${BOLD}════════════════════════════════════════${RESET}"
echo "${GREEN}✓ All quality gates passed${RESET} ${DIM}(${elapsed}s)${RESET}"
echo "${BOLD}════════════════════════════════════════${RESET}"
