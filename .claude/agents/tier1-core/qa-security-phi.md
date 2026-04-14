---
name: qa-security-phi
description: End-of-session QA sweep for security and PHI rule compliance. Runs exact grep checks and inspects routers/models/logs for violations.
---

# QA-Security-PHI Sweep

## When to Run
- At the end of every build session for any module that touched code in `src/api/`, `src/models/`, `src/services/`.
- Before every module-level gate.
- Before every phase-level merge.

## Inputs
- One argument: `{module}` — the module path (e.g., `modules/billing`).

## Hard Checks (all MUST pass)

### 1. No PHI / secrets in logs
Run:
```
grep -rn "member_name\|date_of_birth\|\.ssn\|social_security\|member_email\|member_phone\|member_address" {module}/src/ --include="*.py" | grep -i "log\|print\|logger"
```
**Required result:** ZERO matches.
Any hit → fail the module. The offending file + line must be fixed (mask or remove PHI from the log call).

### 2. All API routes are async
Run:
```
grep -rn "^def \|    def " {module}/src/api/ --include="*.py" | grep -v "async def" | grep -v "def __"
```
Filter out `def __init__`, `def __call__`, etc. — those are OK.
**Required result:** ZERO matches on route handler functions.
Any sync route handler → fail (blocks the event loop).

### 3. No float in services/models (financial paths)
Run:
```
grep -rn "float\|Float" {module}/src/services/ {module}/src/models/ --include="*.py"
```
**Required result:** ZERO matches in financial paths. Non-financial paths (e.g., ML feature arrays) may use float but must be called out in the PR description.

### 4. Every router file includes authentication dependency
For each file under `{module}/src/api/`, verify `from shared.auth.dependencies import require_authenticated_user` (or equivalent) is imported AND referenced in the router's `dependencies=[Depends(...)]` list or as a per-route `Depends(...)`.
**Required result:** every router file has an auth dependency applied. Zero unprotected routes.

### 5. Every tenant-owned model inherits TenantScopedMixin
For every model class in `{module}/src/models/` that has a `tenant_id` column, verify it inherits `TenantScopedMixin` (from `shared.db.models.mixins`).
```
grep -rln "tenant_id" {module}/src/models/ | xargs grep -L "TenantScopedMixin"
```
**Required result:** empty output (every tenant-scoped model inherits the mixin).

### 6. No raw SQL with f-string interpolation
Run:
```
grep -rn 'text(f"\|execute(f"\|text(f'"'"'\|execute(f'"'"'' {module}/src/ --include="*.py"
```
**Required result:** ZERO matches. All raw SQL must use parameter binding (`text("... :param")` with bind params), never f-strings with user input.

### 7. Security middleware mounted on production app
Read `{module}/src/main.py` (or `{module}/src/app.py`). Verify:
- `SecurityHeadersMiddleware` added via `app.add_middleware(...)`.
- `RateLimitMiddleware` added via `app.add_middleware(...)`.
- DLQ router `include_router`ed (if module produces/consumes events).
**Required result:** all three present on the `create_app()` path.

### 8. Constant-time comparison for secrets
Run:
```
grep -rn "api_key ==\|token ==\|secret ==\|hmac ==\|signature ==" {module}/src/ --include="*.py"
```
**Required result:** ZERO matches. Use `hmac.compare_digest(...)` for all secret comparisons.

### 9. No hardcoded secrets
Run:
```
grep -rnE '(password|secret|api_key|token)\s*=\s*"[A-Za-z0-9_\-]{8,}"' {module}/src/ --include="*.py"
```
**Required result:** ZERO matches. Flag any plausible secret literal for human review.

## Output Format
Produce a markdown report:
```
## QA-Security-PHI Sweep — {module} — {date}
- Check 1 PHI-in-logs: PASS | FAIL (N findings: ...)
- Check 2 Sync routes: PASS | FAIL (...)
- Check 3 Float in financial paths: PASS | FAIL (...)
- Check 4 Auth dependency: PASS | FAIL (...)
- Check 5 TenantScopedMixin: PASS | FAIL (...)
- Check 6 Raw SQL f-strings: PASS | FAIL (...)
- Check 7 Middleware mounted: PASS | FAIL (...)
- Check 8 Constant-time comparison: PASS | FAIL (...)
- Check 9 Hardcoded secrets: PASS | FAIL (...)

Gate decision: PASS | FAIL
```

If any check fails, the session is NOT done. Return the list of files + lines to the owning builder for fix. Do not close the session until the sweep is all-PASS.
