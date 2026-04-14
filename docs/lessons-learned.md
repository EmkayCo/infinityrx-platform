# Lessons Learned Log

Entries added by builders during the build. Critical/high severity lessons are propagated to `.claude/rules/` files.

---

### LESSON-008: `after_transaction_end` sync event listener is incompatible with AsyncSession + StaticPool
**Date:** 2026-04-13
**Module:** pharmacy-directory
**Builder:** Builder-PharmacyDirectory
**Severity:** high

**What happened:**
Router tests using `httpx.AsyncClient + ASGITransport` showed 74% branch coverage on `router.py` despite every route being exercised. The SAVEPOINT restart listener (from LESSON-001) was the root cause. When installed on an `AsyncSession` backed by a `StaticPool` SQLite connection, the listener fires synchronous code (`conn.sync_connection.begin_nested()`) from within an async coroutine context. The `aiosqlite` driver executes async IO on the underlying SQLite connection, but `begin_nested()` inside the synchronous `after_transaction_end` event runs outside any greenlet context. This causes the coverage.py C tracer to lose track of the async coroutine frames that resume after `await` suspension points — the tracer sees the coroutine restart but has no frame context to attribute the lines to, so post-`await` lines are recorded as not executed.

Additionally, with `StaticPool` all connections share the same underlying SQLite connection. The synchronous listener firing on one session disrupts the async frame tracking for all sessions using that connection — including sessions from different test functions.

**Root cause:**
`after_transaction_end` is a synchronous SQLAlchemy event. When fired from an `AsyncSession` that has an active async context, calling `conn.sync_connection.begin_nested()` from the listener crosses the async/sync boundary in a way that `aiosqlite` does not support outside a greenlet. This breaks the coverage.py C tracer's coroutine resume tracking rather than raising an explicit error — making it extremely hard to diagnose.

**Fix:**
The SAVEPOINT restart listener is only needed when the code under test calls `db.commit()`. If all route/service handlers call only `db.flush()` (never `db.commit()`), the outer `conn.begin()` + `conn.rollback()` pattern provides complete isolation without a restart listener. Verify the code never calls `commit()` before removing the listener:

```bash
grep -rn "\.commit()" src/   # must return zero results
```

If the code under test does call `commit()`, the fix is to use a separate in-memory engine per test (not StaticPool) so each test gets its own connection, eliminating the shared-connection interference. Alternatively, use `pytest-anyio` with `asyncio_mode=auto` and avoid the SAVEPOINT listener entirely by isolating at the engine level.

**Prevention rule:**
Before adding an `after_transaction_end` listener to an `AsyncSession` fixture: (1) confirm the code calls `commit()`, not just `flush()` — if flush-only, the listener is unnecessary; (2) if the code does commit, use a per-test engine rather than StaticPool to avoid the sync/async boundary crossing.

**Regression test:**
`modules/pharmacy-directory/tests/integration/test_router.py` — 31 router tests all hitting `async def` route handlers post-`await`. If the coverage C tracer regresses, router.py coverage will drop from 100% to ~74%, which would fail the `fail_under = 99` gate.

---

### LESSON-006: Security primitives built-and-tested in isolation but never mounted on the production app
**Date:** 2026-04-13
**Module:** core-platform
**Builder:** Emergency-Wiring
**Severity:** critical

**What happened:**
A comprehensive audit found that tamper-evident audit hashing, MFA, security headers, rate limiting, DLQ inspection, and tenant isolation were each authored with full test coverage in their own subsystems — then never wired into the running FastAPI application. The pattern: 40% of effort went to "design and test the primitive" and 0% went to "mount it on the app that serves traffic."

Concrete examples discovered in the same session:
- `AuditService.log()` at `modules/core-platform/src/audit/service.py:47` wrote rows with `entry_hash=""` — `compute_entry_hash()` existed and had 8 tests but was never called on the write path.
- `SecurityHeadersMiddleware` and `RateLimitMiddleware` had their own integration tests but were absent from `main.py:create_app()`; production responses shipped with no HSTS, CSP, or rate limiting.
- `build_dlq_router` had 18 tests; the router was never `include_router`ed anywhere reachable by a real request.
- `TenantIsolationMiddleware` installed `with_loader_criteria` on the `shared` session factory, but three modules (billing, payment-processing, reclaimrx) each maintained their own `sessionmaker` and never called `install_tenant_loader`.
- `FraudNetworkAnalyzer.GraphEdge.total_amount` was annotated `float` and accumulated dollar amounts across graph edges via IEEE 754 arithmetic, violating the "Decimal only for money" principle — despite the module having `penny_allocate` property tests for its other financial paths.

**Root cause:**
Test discipline was applied at the unit level, so every primitive could ship "with tests" and feel done. Nothing enforced the subsequent integration step: "does the *application* actually call this primitive on the happy path?" Unit tests on a primitive prove the primitive works in isolation; they say nothing about whether the primitive is reachable by a real request. Without an integration contract test (e.g., "issuing 3 audit entries produces an unbroken hash chain on the real AuditService") the gap is invisible.

**Fix:**
For each primitive, write an integration test at the next layer up that can only pass if the primitive is both called and correct. Examples landed in this session:
- `test_service_hash_chain.py::test_three_entries_form_unbroken_chain` verifies `AuditService.log()` populates the chain, not that `compute_entry_hash` works in isolation.
- `test_main_middleware.py::test_security_headers_present_on_responses` drives `TestClient` against `create_app()` and asserts `Strict-Transport-Security` on the response — the only way this passes is if the middleware is mounted.
- `test_graph_analysis_decimal.py::test_graph_edge_default_amount_is_decimal_zero` asserts the dataclass default is Decimal, not float — a statement-level test would have been fooled by `total_amount: float = 0.0`.

**Prevention rule:**
For any new primitive that must run on the request path, the RED test MUST assert the primitive's observable effect through the top-level app (`create_app()` or equivalent), not the primitive in isolation. "Is it mounted?" is a test case, not a code-review checklist item. Candidate file: `.claude/rules/architecture.md` → "Every middleware/router/pre-commit primitive MUST have at least one integration test that exercises it through the top-level application factory. Unit tests on the primitive alone are insufficient; they verify correctness of a component that may never run."

**Regression test:**
`modules/core-platform/tests/test_main_middleware.py` — four tests that fail-closed if SecurityHeadersMiddleware, RateLimitMiddleware, or the DLQ router regress out of `create_app()`.

---

### LESSON-001: SQLite SAVEPOINT isolation required for tests that commit inside routes
**Date:** 2026-04-13
**Module:** reclaimrx
**Builder:** Builder-ReclaimRx
**Severity:** high

**What happened:**
Integration tests using a shared in-memory SQLite engine accumulated state across test cases. A route handler called `db.commit()` inside its business logic, which committed the transaction that the test fixture was relying on for rollback isolation. After the commit, the outer `connection.begin().rollback()` in the fixture teardown rolled back nothing — the data was already durably written to the in-memory DB. Subsequent tests saw rows from prior tests, causing `MultipleResultsFound` errors and false positive/negative results.

**Root cause:**
When a FastAPI route calls `db.commit()`, SQLAlchemy issues a real COMMIT on the underlying connection. A plain `connection.begin()` / `connection.rollback()` at the fixture level cannot roll back changes that were already committed. The fixture needs a mechanism that survives inner commits and can still roll everything back at teardown.

**Fix:**
Use SQLAlchemy SAVEPOINTs (`begin_nested()`) with an `after_transaction_end` event listener that reopens the savepoint after each inner commit. The outer `connection.begin()` is never committed — only rolled back in teardown — so the SAVEPOINT acts as a fence around every test:

```python
@pytest.fixture()
def db(engine) -> Session:
    connection = engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session
    session.close()
    outer.rollback()
    connection.close()
```

**Prevention rule:**
ADDED TO `.claude/rules/testing.md`:
"Any test fixture for code that calls db.commit() inside route/service logic MUST use SQLAlchemy begin_nested() SAVEPOINTs with an after_transaction_end listener. A plain begin()/rollback() pattern does NOT isolate tests when the code under test commits."

**Regression test:**
`test_seed_system_templates_is_idempotent` in `tests/unit/test_letter_service.py` — seeds templates twice; would return duplicate rows if SAVEPOINT isolation were broken, causing the count assertion to fail.

---

### LESSON-002: FastAPI TestClient.delete() does not support a request body
**Date:** 2026-04-13
**Module:** reclaimrx
**Builder:** Builder-ReclaimRx
**Severity:** medium

**What happened:**
A DELETE endpoint was designed to accept a JSON body (`{"reason": "..."}`) for audit purposes. The test used `client.delete(url, json={"reason": "Released"})`. The body was silently ignored — the route received an empty/default reason every time, and subsequent tests using `content=json.dumps(...)` also failed because `httpx` (used by FastAPI TestClient) does not send bodies on DELETE requests.

**Root cause:**
HTTP DELETE with a body is technically allowed by RFC 7231, but many HTTP clients (including httpx/TestClient) strip or ignore the body on DELETE. FastAPI's TestClient inherits this behavior.

**Fix:**
Changed the DELETE endpoint to accept the `reason` as a query parameter instead of a request body:
```python
@router.delete("/holds/{hold_id}")
def release_hold(hold_id: str, reason: str = Query(default="Released"), ...):
```
Tests updated to use `params={"reason": "..."}`.

**Prevention rule:**
None added to rules — medium severity stays as reference.

**Regression test:**
`test_release_hold` in `tests/integration/test_api_endpoints_extended.py` — verifies the DELETE endpoint correctly receives and uses the reason query parameter.

---

### LESSON-005: `logger.extra={"module": ...}` collides with LogRecord built-ins
**Date:** 2026-04-13
**Module:** core-platform (shared.observability + src.main)
**Builder:** Builder-Hardening
**Severity:** high

**What happened:**
After wiring structured JSON logging into `src.main.lifespan`, all four
lifespan tests suddenly raised `KeyError: "Attempt to overwrite 'module' in
LogRecord"`. The failing code was:

```python
logger.info("service_started", extra={"module": "core-platform"})
```

`logging.LogRecord` already has a `module` attribute (set from the caller's
`__name__`), and `Logger.makeRecord` refuses to overwrite any built-in
attribute — it raises rather than silently dropping the value. The
`ContextFilter` added by `configure_logging()` was not at fault; the issue
was latent and only surfaced once the formatter actually serialized records.

**Root cause:**
Python's `logging` reserves these attribute names on every `LogRecord`:
`name, msg, args, levelname, levelno, pathname, filename, module, exc_info,
exc_text, stack_info, lineno, funcName, created, msecs, relativeCreated,
thread, threadName, processName, process, message, asctime`. Any key
passed via `extra={}` that matches one of these raises `KeyError`.

Before JSON logging, most handlers were console-only with free-form format
strings, so the collision still raised — but we simply had not logged
`extra={"module": ...}` anywhere. Adding structured logging encouraged
richer `extra` payloads and surfaced the latent collision.

**Fix:**
Use `"service"` (or any non-reserved key). Updated two call sites in
`src.main`:
```python
logger.info("service_started", extra={"service": "core-platform"})
```

**Prevention rule:**
For any structured log key, avoid the reserved `LogRecord` attribute set.
When in doubt, prefix with the subsystem: `audit_action`, `auth_user_id`,
`svc_name`. Never use bare `module`, `name`, `message`, `asctime`,
`levelname`, `pathname`, `lineno`, `funcName`, `process`, `thread`.

**Regression test:**
The four `test_lifespan_*` cases in
`modules/core-platform/tests/test_main_lifespan.py` now all exercise
`configure_logging` → log emission paths; any reserved-attribute regression
will trip them immediately.

---

### LESSON-004: Python `re.match` with `$` anchor accepts trailing newline
**Date:** 2026-04-13
**Module:** core-platform (shared.auth.mfa.totp)
**Builder:** Builder-Security
**Severity:** high

**What happened:**
The TOTP code-format validator used `re.compile(r"^\d{6}$")` to reject non-6-digit input. Input like `"123456\n"` passed the regex — Python's `$` anchor by default matches *before* a trailing newline, not strictly at end-of-string. An attacker submitting codes with embedded whitespace/newlines could bypass the format gate before reaching `pyotp.TOTP.verify` (which would reject them numerically, but the validator contract was silently broken).

**Root cause:**
`^...$` anchors in Python `re` are not the same as in `re.fullmatch`. `$` matches at end-of-string **or** just before a terminating newline. This is documented but easy to miss when porting patterns from other languages or when code review treats the anchor pair as meaning "whole string only."

**Fix:**
Replaced `r"^\d{6}$"` with `r"\A\d{6}\Z"` — `\A` and `\Z` are strict start/end-of-string anchors regardless of multiline flag or trailing newlines. Equivalent alternative: switch from `re.match(...)` to `re.fullmatch(...)`.

**Prevention rule:**
Should be added to `.claude/rules/security.md` (or similar) once that file exists: "For any input-format validator, use `\A...\Z` anchors or `re.fullmatch`. `^...$` with `re.match` accepts trailing newlines and is unsafe for security-boundary validation."

**Regression test:**
`test_verify_totp_malformed_raises[123456\n]` in `shared/tests/auth/mfa/test_totp.py` — submits a 6-digit code with trailing newline; must raise `InvalidTotpFormat`.

---

### LESSON-007: PG_UUID(as_uuid=True) returns float under SQLite SAVEPOINT sessions
**Date:** 2026-04-14
**Module:** member-management
**Builder:** member-management
**Severity:** medium

**What happened:**
After adding SAVEPOINT-based test isolation (per LESSON-001) to the member-management module, every test that read back an `Accumulator` row via `db.query(Accumulator).filter_by(...).first()` crashed with:

```
AttributeError: 'float' object has no attribute 'replace'
```

The UUID column `tenant_id` was receiving `1.1111111111111112e+31` — i.e., the UUID `11111111-1111-1111-1111-111111111111` interpreted as a Python float.

**Root cause:**
`PG_UUID(as_uuid=True)` stores UUID values as raw bytes (BLOB) in SQLite. Under a normal `Session`, SQLAlchemy fetches BLOBs and its `UUID` type processor correctly converts them to `uuid.UUID` objects. Under a SAVEPOINT-based connection (using `join_transaction_mode="create_savepoint"`), SQLite's pysqlite driver appears to return BLOB data as Python floats in some result rows — most likely because the C-level row factory in the `cyextension` path applies integer-style coercion to 16-byte BLOBs when no explicit type affinity is set on the SQLite column.

The `INSERT` side was unaffected; the crash only manifested on `SELECT` after an earlier flush within the same SAVEPOINT connection.

**Fix:**
In the conftest `_engine` fixture, replace all `PG_UUID` columns with a `_UUIDString` TypeDecorator that stores as `VARCHAR(36)` and round-trips `uuid.UUID` ↔ str explicitly:

```python
class _UUIDString(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None

# In _engine fixture, after nulling schemas:
for col in table.columns:
    if isinstance(col.type, JSONB):
        col.type = JSON()
    elif isinstance(col.type, PG_UUID):
        col.type = _UUIDString()
```

**Prevention rule:**
ADDED TO `.claude/rules/testing.md` (see LESSON-007 section).

**Regression test:**
`test_apply_claim_ledger_row_created` in `modules/member-management/tests/unit/test_accumulator_db.py` — the anchor test seeds an Accumulator and queries it back in the same SAVEPOINT session; any regression in the UUID type swap will immediately fail with the float AttributeError.

---

### LESSON-003: penny_allocate remainder can be negative — first item absorbs it
**Date:** 2026-04-13
**Module:** reclaimrx
**Builder:** Builder-ReclaimRx
**Severity:** medium

**What happened:**
Property-based tests for `penny_allocate` made two incorrect assumptions:
1. All items differ by at most 1 penny (false when total < per_item × count, e.g., 0.02 / 4 = 0.005 rounds to 0.01 each, but 4 × 0.01 > 0.02, so remainder = -0.02 and first item = -0.01 while others = 0.01 — a difference of 0.02).
2. The first item is always ≥ the other items (false for the same negative-remainder case).

**Root cause:**
The algorithm computes `per_item = round(total / count, 2)` then `remainder = total - per_item * count`. When `per_item` rounds up, the remainder is negative, and `items[0] = per_item + remainder` is smaller than `items[1:]`. The tests assumed "first item absorbs extra" without considering the negative case.

**Fix:**
Replaced the incorrect invariant tests with:
- `test_penny_allocate_non_first_items_are_equal`: items[1:] are all identical to each other (the remainder only touches index 0).
- `test_penny_allocate_first_item_absorbs_remainder`: verifies the exact formula `items[0] == per_item + remainder`.

**Prevention rule:**
None added to rules — medium severity stays as reference.

**Regression test:**
`test_penny_allocate_non_first_items_are_equal` and `test_penny_allocate_first_item_absorbs_remainder` in `tests/property/test_financial_invariants.py`.
