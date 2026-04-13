# Lessons Learned Log

Entries added by builders during the build. Critical/high severity lessons are propagated to `.claude/rules/` files.

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
