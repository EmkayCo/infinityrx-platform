# Testing Rules (Mandatory — All Modules)

## Coverage Requirements
- 100% test coverage on ALL financial logic (calculations, Decimal operations, fee splits, payment amounts, ledger entries)
- 100% test coverage on ALL PHI paths (masking, access logging, tenant isolation, encryption)
- 100% test coverage on ALL security paths (auth, authorization, input validation)
- 95% test coverage on all other active code
- Coverage measured ONLY on modules with actual implementation
- Exclude unimplemented modules from coverage config (pyproject.toml)
- Reported coverage must reflect reality — no inflated numbers from empty files

## Test Execution Rules
- Every test must pass — zero failures, zero skips, zero expected failures
- Tests run BEFORE marking any task complete
- If any test fails, fix it before moving to the next task
- Integration tests run after all teammates merge
- No task is done until tests prove it works with real/sample data

## Dead Code / Stub File Scanner
At every gate review, verify:
- No empty placeholder files for modules not in the current phase
- No pass-only or NotImplementedError-only files
- No commented-out code blocks
- No TODO/FIXME without a linked task in tasks/todo.md
- If a module isn't being built this phase, its files should not exist (only the folder structure)

Delete any empty stub/placeholder files that exist now.

## SQLAlchemy Test Isolation (LESSON-001 — High Severity)
Any test fixture for code that calls `db.commit()` inside route or service logic MUST use SQLAlchemy `begin_nested()` SAVEPOINTs with an `after_transaction_end` event listener that reopens the savepoint after each inner commit. A plain `begin()` / `rollback()` pattern does NOT isolate tests when the code under test commits — the outer rollback has nothing to roll back and all test data leaks into subsequent tests.

Required fixture pattern:
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

Symptoms of broken isolation: `MultipleResultsFound`, rows persisting across tests, idempotency tests failing on second seed call.
