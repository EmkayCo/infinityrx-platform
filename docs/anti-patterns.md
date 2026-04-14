# Anti-Pattern Registry

Builders must NEVER do any of the following. Each entry references the rule files that forbid it.

## AP-001: Write code then tests
**Why it's bad:** Confirms the implementation you wrote, not the behavior you needed. Tests fit the code instead of driving it.
**What to do instead:** Write the test first, watch it fail (RED), then write the minimum code to make it pass (GREEN), then refactor. Git history must show the test commit before the implementation commit.

## AP-002: `# type: ignore`
**Why it's bad:** Silences the type checker rather than fixing the underlying type problem; lies accumulate.
**What to do instead:** Fix the annotation, refine the Protocol/TypedDict, or narrow with `isinstance` / `cast`. If a library is truly untyped, add a local `.pyi` stub instead of suppressing.

## AP-003: `# noqa`
**Why it's bad:** Hides lint errors; the next person sees clean output while the code drifts.
**What to do instead:** Fix the lint issue. If the rule is genuinely wrong for this project, disable it globally in `pyproject.toml` with a comment explaining why.

## AP-004: `except Exception: pass`
**Why it's bad:** Swallows every error silently — the system looks healthy while data is being corrupted.
**What to do instead:** Catch the specific exception type; log with structured context (`correlation_id`, `tenant_id`, `entity_id`); re-raise or return a structured error response.

## AP-005: `float(amount)` in financial paths
**Why it's bad:** IEEE 754 drift. `0.1 + 0.2 != 0.3`. With billions of dollars and 100M+ claims, drift becomes real money lost or gained.
**What to do instead:** `Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`. See `.claude/rules/financial-precision.md`.

## AP-006: Raw SQL with f-strings
**Why it's bad:** SQL injection. Even "internal" endpoints get exposed.
**What to do instead:** SQLAlchemy ORM, or `text("SELECT ... WHERE x = :x")` with bound parameters. Never interpolate user input into query text.

## AP-007: `print()` for debugging
**Why it's bad:** Not structured, not searchable, not routed to the log aggregator, and frequently left behind in production.
**What to do instead:** `logger.debug("event_name", extra={"svc_name": ..., "entity_id": ...})`. Remove before commit if truly temporary.

## AP-008: Skip a failing test
**Why it's bad:** `@pytest.mark.skip` hides a real bug behind a green CI. The reason for the skip rots; the bug remains.
**What to do instead:** Fix the code, or fix the test to reflect the actual (correct) behavior. If the feature is deferred, delete the test until the feature returns.

## AP-009: Hardcode `tenant_id`
**Why it's bad:** Breaks multi-tenancy the moment a second tenant onboards. A subtle single-tenant assumption embedded deep in a service is one of the worst bugs to unwind.
**What to do instead:** Always resolve from `shared.db.tenant_context.current_tenant_id` populated by `TenantIsolationMiddleware`. See `.claude/rules/tenant-isolation.md`.

## AP-010: Copy-paste service logic across modules
**Why it's bad:** Two copies drift; bugs get fixed in one and not the other. `penny_allocate` is the canonical example — three copies means three differently-buggy splits.
**What to do instead:** Extract to `shared/` the first time you need it in a second place. Delete the module-local copy in the same commit.

## AP-011: Comment out broken code
**Why it's bad:** Dead code accumulates; future readers can't tell if it's load-bearing, experimental, or just forgotten.
**What to do instead:** Delete it. Git has history. If you genuinely need to preserve the snippet for later, write an issue or TODO with a linked task.

## AP-012: Test implementation details instead of behavior
**Why it's bad:** Tests break on refactor even when behavior is unchanged. Assertions on private method calls, internal state, or specific query counts tie the test to the code shape.
**What to do instead:** Test the contract: given these inputs, the observable outputs (return value, DB state, emitted events) are X. Let the internals refactor freely.

## AP-013: Mock everything instead of using real DB for integration tests
**Why it's bad:** Tests pass while the real database rejects the query. Migrations, constraints, index behavior, and RLS go untested. See LESSON-001 for what this cost us.
**What to do instead:** Integration tests use a real PostgreSQL (testcontainers or an ephemeral schema) with the SAVEPOINT-based fixture pattern from `.claude/rules/testing.md`. Mock only at true boundaries (third-party HTTP APIs, time).
