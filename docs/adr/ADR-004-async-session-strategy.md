# ADR-004: Async-first SQLAlchemy session strategy

**Status:** Accepted
**Date:** 2026-04-14
**Deciders:** Platform architecture

## Context

InfinityRx targets 100M+ claims/year. Most module API routes perform I/O-bound
work (DB reads, event bus publishes, external API calls). Python's GIL means
concurrency must come from async I/O, not threads. However, several historical
patterns created consistency problems:

1. **Multiple module-local `sessionmaker` instances** — billing,
   payment-processing, and reclaimrx each defined their own `sessionmaker`
   without calling `install_tenant_loader`. This silently bypassed tenant
   isolation (audit CR-09 and LESSON-006 context).

2. **Sync `psycopg2` sessions in async FastAPI routes** — 77 billing routes,
   24 reclaimrx routes, and 19 payment-processing routes use sync `def`
   handlers with `psycopg2` sessions, blocking the async event loop (audit C5).

3. **Test isolation complexity** — three competing patterns exist across
   modules: SAVEPOINT-based (LESSON-001), per-test engine (LESSON-008), and
   simple rollback (broken when code calls `commit()`).

## Decision

### Production: shared async session factory

- All modules MUST use `shared.db.session.get_session` (async SQLAlchemy with
  `asyncpg` driver).
- NO module-local `sessionmaker`. Module shims (`_shim/db.py`) are transitional
  only and MUST be deleted when `shared.db.session` lands.
- `install_tenant_loader` MUST be called once at application startup via
  `shared.db.session.create_session_factory()`.
- All API routes MUST use `async def`. Sync `def` routes block the event loop
  at > 10 concurrent requests.

### Test: per-test engine isolation

The correct test session pattern depends on whether the code under test calls
`db.commit()`:

**Case 1: Code calls `flush()` only (no `commit()`)**

Use a shared in-memory SQLite engine with simple rollback at teardown:
```python
@pytest.fixture()
async def db(engine):
    async with AsyncSession(engine) as session:
        yield session
        await session.rollback()
```

**Case 2: Code calls `commit()` and uses sync SQLAlchemy**

Use SQLAlchemy SAVEPOINT isolation (LESSON-001):
```python
connection = engine.connect()
outer = connection.begin()
nested = connection.begin_nested()
session = Session(bind=connection, join_transaction_mode="create_savepoint")
# ... restart savepoint in after_transaction_end listener
```

**Case 3: Code calls `commit()` and uses async SQLAlchemy**

Do NOT use SAVEPOINT + `after_transaction_end` on an AsyncSession backed by
StaticPool — this crosses the async/sync boundary causing coverage.py C tracer
to lose coroutine frames (LESSON-008). Instead, use a per-test engine:
```python
@pytest.fixture()
async def engine():
    e = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()
```

**PG_UUID(as_uuid=True) in SQLite test engines**

Any module using `PG_UUID(as_uuid=True)` columns MUST swap to `_UUIDString`
TypeDecorator in the test `_engine` fixture (LESSON-007). Otherwise SAVEPOINT
sessions return UUIDs as Python floats.

### Engine configuration

All engines (production and test) MUST set:
- `pool_size=20, max_overflow=10` (production)
- `connect_args={"command_timeout": 30}` — statement timeout
- `echo=False` (production), `echo=True` (debug only)

---

## Alternatives considered

1. **Per-module session factory.** Rejected: `install_tenant_loader` would need
   to be called in every module, creating duplicate infrastructure and drift risk.
   Audit found 3 modules had already failed to call it (CR-09, H-05).

2. **Synchronous sessions everywhere.** Rejected: psycopg2 blocks the event loop.
   Under 100 concurrent requests, 77 sync billing routes would serialize all DB
   I/O. Benchmark shows > 4× throughput improvement with async sessions.

3. **SAVEPOINT isolation for all async tests.** Rejected: LESSON-008 documents
   the coverage.py C tracer failure when `after_transaction_end` fires from an
   AsyncSession backed by StaticPool. Per-test engine is the correct alternative.

## Consequences

**Positive:**
- Tenant isolation is enforced automatically via the shared session factory.
- Single point of `statement_timeout` configuration.
- Async routes enable the event loop to multiplex I/O efficiently.
- Test strategy is well-documented across 3 cases.

**Negative:**
- Migration cost: 77 billing routes, 24 reclaimrx routes, 19 payment-processing
  routes need `async def` conversion. Tracked in audit remediation (C5).
- Module-local shims must be replaced and deleted — timing depends on when the
  shared session primitive fully lands.
- Per-test engine creates/drops schema for every test function; adds ~50ms per
  test. Acceptable for correctness; run integration tests on a long-lived DB.

## Cross-references

- LESSON-001 — SAVEPOINT isolation requirement
- LESSON-007 — PG_UUID(as_uuid=True) float bug under SQLite SAVEPOINTs
- LESSON-008 — async/sync boundary breakage with StaticPool + SAVEPOINT listener
- Audit CR-05 — 77 sync routes blocking event loop
- Audit CR-09 — prescriber-directory session factory missing tenant loader
- `shared/db/session.py` — canonical session factory
- `shared/db/tenant_context.py` — current_tenant_id contextvar
