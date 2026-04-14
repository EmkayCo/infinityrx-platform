---
name: qa-financial-data
description: End-of-session QA sweep for financial precision and data integrity. Runs exact grep checks on Decimal usage, aggregates, penny allocation, and money columns.
---

# QA-Financial-Data Sweep

## When to Run
- At the end of every build session for Billing, Payment Processing, ReclaimRx, Reporting, DataIQ.
- Before every module-level gate for any module that touches dollar amounts.
- Before every phase-level merge.

## Inputs
- One argument: `{module}` — the module path (e.g., `modules/billing`).

## Hard Checks (all MUST pass)

### 1. No float/Float in services or models — instant FAIL if found
Run:
```
grep -rn "float\|Float" {module}/src/services/ {module}/src/models/ --include="*.py"
```
**Required result:** ZERO matches.
ANY hit in a financial path is an instant FAIL for the entire module. Legitimate non-financial float use (ML feature arrays, SPC sigma calc, geo distance) must live OUTSIDE `services/` and `models/` — typically under `src/ml/` or `src/analytics/` — and be explicitly approved in a code-review note.

### 2. Every .quantize() specifies ROUND_HALF_UP
Run:
```
grep -rn "\.quantize(" {module} --include="*.py" | grep -v "ROUND_HALF_UP"
```
**Required result:** ZERO matches.
Any `.quantize()` call without `rounding=ROUND_HALF_UP` relies on Python's default `ROUND_HALF_EVEN` — wrong for money.

### 3. SQLAlchemy aggregates wrapped in Decimal
Run:
```
grep -rn "func\.sum\|func\.avg" {module} --include="*.py" | grep -v "Decimal(str("
```
**Required result:** ZERO matches.
`func.sum` and `func.avg` return float from SA's type layer; every use must wrap: `Decimal(str(db.scalar(func.sum(...))))`.

### 4. penny_allocate imported from shared, not module-local
Run:
```
grep -rn "def penny_allocate\|def _penny_allocate" {module}/src/ --include="*.py"
```
**Required result:** ZERO matches (no local definition).
Then:
```
grep -rn "from shared.utils.money import" {module}/src/ --include="*.py" | grep "penny_allocate"
```
**Required result:** every file that splits amounts imports `penny_allocate` from `shared.utils.money`.

### 5. All money columns are Numeric, not Float/REAL
For every model file in `{module}/src/models/`, verify columns named `amount`, `price`, `cost`, `fee`, `total`, `balance`, `rate`, `paid`, `billed`, `*_cents`, `*_usd`:
```
grep -rn "amount\|price\|cost\|fee\|total\|balance" {module}/src/models/ --include="*.py" | grep -iE "Float|REAL|sa\.Float"
```
**Required result:** ZERO matches.
All money columns: `sa.Numeric(x, 2)` for dollars-and-cents, `sa.Numeric(x, 4)` for sub-cent rates.

### 6. Decimal in event payloads serialized as str
For every event publisher, verify amount fields are serialized as `str(decimal_value)`:
```
grep -rn "EventEnvelope\|publish_event\|emit_event" {module}/src/ --include="*.py" -A 10 | grep -E "amount|price|cost|total" | grep -v "str(" | grep -v "#"
```
Inspect hits — any amount passed directly (not via `str()`) fails.
**Required result:** every amount field in event payload code is wrapped with `str(...)`.

### 7. Batch totals verified against components
For every batch/invoice generation service, grep for the balance-check test:
```
grep -rn "sum(\|assert.*==.*total\|assert.*total.*==" {module}/tests/ --include="*.py"
```
Manually verify a test exists that asserts `batch_total == sum(component_amounts)` for each generation path. Missing test → FAIL.

### 8. Foreign keys present on references
For every model with a `*_id` column pointing to another table, verify a `ForeignKey` constraint is declared in the column definition:
```
grep -rn "Column(.*_id.*)" {module}/src/models/ --include="*.py" | grep -v "ForeignKey\|primary_key"
```
**Required result:** ZERO matches (every `*_id` column has a FK or is a primary key).

### 9. Unique constraints on natural keys
Inspect each model; every natural-key combination (e.g., `(tenant_id, external_id)`, `(tenant_id, claim_number)`) must have a `UniqueConstraint` or `Index(unique=True)`.
Produce a list of tables missing a uniqueness constraint on the obvious natural key.
**Required result:** zero missing constraints.

### 10. Transactions wrap multi-step operations
For every service function that writes to more than one table, verify the function opens a transaction (`session.begin()` or is called within one) and commits at the end. Functions that split `.commit()` across multiple writes without a wrapping transaction FAIL.

## Output Format
```
## QA-Financial-Data Sweep — {module} — {date}
- Check 1 No float in services/models: PASS | FAIL (...)
- Check 2 quantize ROUND_HALF_UP: PASS | FAIL (...)
- Check 3 Aggregates wrapped Decimal: PASS | FAIL (...)
- Check 4 penny_allocate from shared: PASS | FAIL (...)
- Check 5 Money columns Numeric: PASS | FAIL (...)
- Check 6 Event amounts str-serialized: PASS | FAIL (...)
- Check 7 Batch total balance tests: PASS | FAIL (...)
- Check 8 Foreign keys present: PASS | FAIL (...)
- Check 9 Unique constraints on natural keys: PASS | FAIL (...)
- Check 10 Transactions wrap multi-write: PASS | FAIL (...)

Gate decision: PASS | FAIL
```

If any check fails, the session is NOT done. Return the list of files + lines to the owning builder. Check 1 failing is a BLOCKER for any further work on the module.
