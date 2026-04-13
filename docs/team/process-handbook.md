# InfinityRx Platform — Team & Process Handbook v3 (FINAL)

**Purpose:** Complete operational handbook for Phase 2 concurrent build. Covers team structure, testing strategy, debugging playbook, process optimization, and quality gates.  
**Target:** 99%+ coverage, zero financial errors, zero PHI leaks, zero cross-tenant leaks.

---

## 1. TEAM STRUCTURE (Unchanged from v2)

```
Team Lead (your Claude Code session)
    ├── Teammate 1: Builder-Billing         (worktree: modules/billing)
    ├── Teammate 2: Builder-Payment-Proc    (worktree: modules/payment-processing)
    ├── Teammate 3: Builder-ReclaimRx       (worktree: modules/reclaimrx)
    └── Teammate 4: Builder-Reporting       (worktree: modules/reporting)

Post-session sweeps:
    ├── QA-Security-PHI (subagent)
    └── QA-Financial-Data (subagent)

On-demand specialists:
    └── EDI, 340B, Accumulator, Workers Comp, Medicare Part D, State Regulatory, DBA
```

---

## 2. MODULE SCAFFOLD (Every Module Starts From This)

Before any builder writes a single line of business logic, the team lead generates a module scaffold. This ensures consistent structure across all 4 modules and eliminates wasted time on boilerplate.

```
modules/{module_name}/
├── __init__.py
├── README.md                              # Auto-generated from PRD section 1
├── api/
│   ├── __init__.py
│   ├── router.py                          # FastAPI APIRouter with prefix
│   ├── dependencies.py                    # Dependency injection (DB session, current user, tenant)
│   └── schemas/                           # Pydantic request/response models
│       └── __init__.py
├── models/
│   ├── __init__.py
│   └── tables.py                          # SQLAlchemy models (from PRD data model)
├── services/
│   ├── __init__.py
│   └── {domain_service}.py               # Business logic (never in routes)
├── events/
│   ├── __init__.py
│   ├── publishers.py                      # Event publishing functions
│   └── consumers.py                       # Event handlers
├── jobs/
│   ├── __init__.py
│   └── scheduled.py                       # Cron jobs for this module
├── migrations/
│   └── versions/                          # Alembic migrations namespaced to module
├── tests/
│   ├── __init__.py
│   ├── conftest.py                        # Module-specific fixtures
│   ├── unit/
│   │   └── __init__.py
│   ├── integration/
│   │   └── __init__.py
│   ├── property/                          # Hypothesis property-based tests
│   │   └── __init__.py
│   └── golden/                            # Golden master files for file output verification
│       └── README.md
└── utils/
    ├── __init__.py
    └── constants.py
```

**Shared utilities live in `core/`:** encryption, Decimal helpers, date/timezone helpers, pagination, error responses. Modules import from core — never duplicate.

---

## 3. TESTING STRATEGY

### 3.1 Test Pyramid

```
         ╱    E2E     ╲          5% — Cross-module workflows (post-merge only)
        ╱  Integration  ╲       25% — API endpoints, DB operations, event bus
       ╱   Property-Based ╲    10% — Hypothesis tests on financial math invariants
      ╱      Unit Tests      ╲ 60% — Service logic, validators, pure functions
```

### 3.2 Coverage Targets

| Category | Target | Enforcement |
|----------|--------|-------------|
| Financial calculations (Decimal math, fee splits, penny allocation, totals) | **100%** | pytest-cov with `--cov-fail-under`. CI blocks merge if below. |
| PHI handling (encryption, masking, access logging) | **100%** | Explicit test per PHI field per operation |
| Security/auth (authentication, authorization, tenant isolation) | **100%** | Automated cross-tenant isolation test suite |
| Business logic (services, domain rules, state machines) | **99%** | Branch coverage, not just line coverage |
| API endpoints (routes, validation, error responses) | **99%** | Every endpoint tested: happy path + error path + auth |
| Event handling (publish, consume, DLQ) | **95%** | Integration test with real RabbitMQ (Docker) |
| Utilities, config, serialization | **95%** | Standard pytest |
| **Overall module** | **99%+** | `pytest --cov=modules/{name} --cov-branch --cov-fail-under=99` |

### 3.3 Test Types (What Each Builder Must Write)

**Unit tests** (60% of tests):
- Test service functions in isolation
- Mock database and external dependencies
- One test per behavior, not per method
- Test names describe the behavior: `test_fee_split_allocates_remainder_penny_to_first_item`
- Edge cases: null, empty, zero, negative, boundary, maximum, concurrent

**Integration tests** (25% of tests):
- Test API endpoints with real database (test PostgreSQL in Docker)
- Test database operations (insert, query, update, constraints)
- Test event publishing and consuming with real RabbitMQ
- Test file generation and parsing (NACHA, 835, Excel)
- Use `TestClient` from FastAPI with `httpx`
- Database reset between tests via transaction rollback (not truncate — faster)

**Property-based tests** (10% of tests — CRITICAL for financial modules):
- Use `hypothesis` library
- Test mathematical invariants that must ALWAYS hold:
  - `sum(split_amounts) == original_amount` for ANY input amount and ANY number of splits
  - `batch_total == sum(payment_amounts)` for ANY set of claims
  - `invoice_total == claims_subtotal + fees_subtotal + adjustments` ALWAYS
  - `prefund_balance_after == prefund_balance_before - batch_total` ALWAYS
  - `Decimal(str(amount)) == amount` for ANY financial amount (no float contamination)
  - `encrypt(decrypt(value)) == value` for ANY PHI value (roundtrip)
- Hypothesis runs hundreds of random inputs per test — catches edge cases humans miss

**Golden master tests** (for file output — NACHA, 835, Excel, PDF):
- Generate a file from known test data
- Compare byte-for-byte against a golden master file stored in `tests/golden/`
- If the output changes, the test fails — developer must verify the change is intentional and update the golden master
- Prevents silent regressions in file format compliance

**Contract tests** (for inter-module events):
- Verify that published event payloads match the schema documented in `docs/api-contracts/`
- Verify that consumer can parse publisher's payload without error
- Run as integration tests with real event bus
- Both publisher and consumer modules run contract tests — if either changes the schema, the other's test fails

### 3.4 Test Data Management

**Factories, not fixtures:**
- Use `factory_boy` library to generate test data
- Each model has a factory: `ClaimRecordFactory`, `APRecordFactory`, `InvoiceFactory`
- Factories produce valid data by default — override specific fields per test
- Factories use `Decimal` for all money fields (never float)
- Factories produce realistic data (valid NPIs, valid NDCs, valid dates)

**Claim data generator:**
- Utility that generates N realistic claims with configurable parameters:
  - Number of pharmacies, prescribers, members, NDCs
  - Date range
  - Amount distribution (normal distribution around configurable mean)
  - Reversal rate (configurable %)
  - Programs and routing rules applied
- Used for: integration tests, load tests, demo data, QA scenarios
- Output: list of `ClaimRecord` objects ready for ingestion

### 3.5 Pre-Commit Quality Gates

Every commit triggers (via pre-commit hooks or CI):

```
1. ruff check .                     # Linting (replaces flake8, faster)
2. ruff format --check .            # Formatting (replaces black, faster)
3. mypy modules/{name} --strict     # Type checking (strict mode)
4. pytest modules/{name}/tests/     # All tests
5. pytest --cov=modules/{name} --cov-branch --cov-fail-under=99  # Coverage
6. safety check                     # Dependency vulnerabilities
7. grep -rn "float\|Float" modules/{name}/services/ modules/{name}/models/  # Float detection
```

Step 7 is a custom check: if `float` or `Float` appears anywhere in service or model files, the commit is REJECTED. All money must be Decimal.

---

## 4. DEBUGGING PLAYBOOK

### 4.1 Error Classification

When a builder encounters an error, classify it first:

| Type | Symptoms | Action |
|------|----------|--------|
| **Build error** | Import fails, syntax error, missing dependency | Fix immediately — don't proceed with broken imports |
| **Test failure** | Existing test breaks after code change | Read the test name (it describes expected behavior). Understand WHY it fails before changing the test or the code. |
| **Type error** | mypy reports type mismatch | Fix the type annotation or the code — never ignore mypy errors |
| **Financial precision error** | Decimal mismatch, penny rounding issue | STOP. This is high severity. Trace the full calculation chain. Verify every intermediate step uses Decimal/ROUND_HALF_UP. |
| **Tenant isolation error** | Cross-tenant data visible | STOP. This is critical. Verify middleware, ORM filter, RLS policy, and cache scoping. |
| **Integration error** | Event not received, API contract mismatch | Check event schema version. Check API contract doc. Run contract tests. |
| **Performance issue** | Query >1 second, endpoint >500ms | Run EXPLAIN ANALYZE. Check for missing index, N+1 query, or full table scan. |

### 4.2 Debugging Process

```
1. READ the error message completely (don't skim)
2. REPRODUCE with a minimal test case
3. ISOLATE — is it in the service layer, the DB layer, or the API layer?
4. TRACE — follow the data from input to error point
5. FIX — minimal change that fixes the root cause (not a symptom)
6. TEST — write a test that would have caught this bug (regression test)
7. VERIFY — run the full test suite to confirm no regressions
```

### 4.3 Debugging Tools

| Tool | When to Use |
|------|-------------|
| `pytest -x --pdb` | Drop into debugger on first test failure |
| `pytest -k "test_name"` | Run a single specific test |
| `EXPLAIN ANALYZE` | Slow database query — see the query plan |
| `redis-cli MONITOR` | See all Redis commands in real-time |
| `rabbitmqctl list_queues` | Check event bus queue depth |
| Structured JSON logs | Search by `correlation_id` to trace a request across modules |
| `mypy --show-error-codes` | Understand exactly which type rule is violated |

### 4.4 When a Builder Gets Stuck

If a builder can't resolve an issue within 15 minutes:

1. **Document what was tried** — in a comment in the code or a note in the task list
2. **Notify team lead** — describe the issue, what was tried, and what the blocker is
3. **Team lead options:**
   - Call a domain specialist subagent for expertise
   - Reassign the task to another builder
   - Simplify the task scope and defer the hard part
4. **Never:** silently skip a failing test, comment out broken code, or reduce coverage to pass the gate

---

## 5. PROCESS OPTIMIZATION

### 5.1 Task Granularity

Each task should be completable in **one builder session** (roughly 30-60 minutes of agent work). Rules:

- **Too big:** "Implement the AP engine" — this is a full subsystem, not a task
- **Right size:** "Implement AP record creation from classified claims with unit tests" — one service function + its tests
- **Too small:** "Add the `amount` field to the AP model" — this is part of a larger task, not standalone

**Task template:**
```
Task: {short description}
Module: {module name}
Files: {which files this task creates or modifies}
Depends on: {task IDs that must complete first}
Tests: {what tests to write}
Done when: {specific acceptance criteria}
```

### 5.2 Build Order Within Each Module

Follow the PRD's session decomposition, but within each session, build in this order:

```
1. Models (SQLAlchemy tables, Alembic migration)
2. Schemas (Pydantic request/response models)
3. Service functions (business logic — TDD: write test, then implement)
4. API routes (thin — call service functions, handle HTTP concerns only)
5. Events (publishers and consumers)
6. Jobs (scheduled tasks)
7. Integration tests (API endpoints with real DB)
8. Property-based tests (financial invariants)
9. Golden master tests (file output verification)
```

This order ensures each layer builds on a stable foundation.

### 5.3 Commit Strategy

Builders commit after each COMPLETED task (not after each file):

```
git add -A
git commit -m "{module}: {task description}

- {what was implemented}
- {test count}: X unit, Y integration, Z property
- Coverage: XX.X%"
```

Commit messages are descriptive. No "WIP" or "fix" commits. Each commit should leave the module in a PASSING state (all tests pass, coverage above threshold).

### 5.4 Session Management (Context Overflow)

When a builder's context window fills up:

1. **Commit current work** — everything passing, all tests green
2. **Write a handoff note** in the module's README or a `HANDOFF.md`:
   - What was completed
   - What's next (reference task list)
   - Any known issues or decisions made
   - Current test count and coverage
3. **Team lead spawns a new session** for the same module
4. **New session reads:** CLAUDE.md + rules + builder agent file + PRD + HANDOFF.md
5. **New session continues** from where the previous left off

### 5.5 Merge Strategy

After each build session (or at session end):

1. Builder commits and pushes to their worktree branch
2. Team lead pulls all branches
3. Integration coordinator (team lead role) merges branches sequentially:
   - Billing first (other modules depend on it)
   - Payment Processing second (depends on Billing events)
   - ReclaimRx third (depends on Billing events)
   - Reporting last (reads from all other modules)
4. Run cross-module integration tests after merge
5. If merge conflict: team lead resolves (conflicts should be rare if file ownership is clean)

### 5.6 Progress Tracking

Team lead maintains a shared task list (Markdown file in repo root):

```markdown
# Phase 2 Build Progress

## Billing (Builder 1)
- [x] Claims ingestion models + migration
- [x] Routing rules engine
- [ ] AP record creation (IN PROGRESS)
- [ ] Payment batch generation
...
Coverage: 99.2% | Tests: 147 passing

## Payment Processing (Builder 2)
- [x] Vendor adapter interface
- [ ] NACHA file generator (IN PROGRESS)
...
Coverage: 98.8% | Tests: 89 passing
```

Updated by each builder at the end of each task. Team lead reviews periodically.

---

## 6. QUALITY GATES

### 6.1 Task-Level Gate (Every Task)

Builder self-checks before marking task complete:

```
□ All new code has tests (TDD — tests written first)
□ All tests pass
□ Coverage ≥ 99% for this task's code
□ mypy passes with zero errors
□ ruff check passes
□ No float/Float in financial paths
□ No PHI in logs or error messages
□ Tenant isolation enforced on new endpoints
□ Audit logging on new mutating endpoints
□ Error responses follow standard format
□ API schemas documented (Pydantic models serve as docs)
```

### 6.2 Session-Level Gate (End of Build Session)

QA sweeps run as subagents:

**QA-Security-PHI sweep:**
```
□ grep for PHI field names in log statements → must find ZERO
□ Every endpoint requires auth (no unprotected routes)
□ Every endpoint enforces tenant_id scoping
□ PHI fields encrypted in model definitions
□ Security headers middleware active
□ Rate limiting configured
□ Input validation (Pydantic) on every request body
□ No raw SQL strings with user input (parameterized only)
```

**QA-Financial-Data sweep (Billing, Payment, ReclaimRx only):**
```
□ grep -rn "float\|Float" in services/ and models/ → must find ZERO
□ Every Decimal operation specifies ROUND_HALF_UP
□ Penny allocation algorithm used for all splits
□ Property-based tests exist for all financial invariants
□ Batch totals verified against sum of components
□ Golden master tests exist for all file outputs
□ Foreign keys on all references
□ Unique constraints on natural keys
□ Transactions wrap multi-step operations
```

### 6.3 Module-Level Gate (Module Complete)

Before declaring a module done:

```
□ All PRD sections implemented (cross-reference against PRD table of contents)
□ All API endpoints from PRD implemented and tested
□ All events from PRD published and consumed
□ All pre-built defaults from PRD populated (detection rules, fee types, return codes, etc.)
□ All test scenarios from PRD covered
□ Coverage ≥ 99% (branch coverage, not just line)
□ Zero mypy errors
□ Zero ruff errors
□ All golden master tests passing
□ All property-based tests passing (100+ examples each)
□ All contract tests passing (event schemas match docs)
□ Performance requirements met (from PRD performance section)
□ README complete with: purpose, setup, API overview, configuration
□ Module can be imported and started independently
```

### 6.4 Phase-Level Gate (All 4 Modules Merged)

After merging all modules:

```
□ Cross-module integration tests pass:
   - Billing emits payment_batch.submitted → Payment Processing receives and processes
   - ReclaimRx emits fwa.payment_hold_placed → Billing holds affected APs
   - Reporting reads from Billing journal → produces correct financial reports
   - All event schemas match between publisher and consumer
□ Combined coverage ≥ 99%
□ No circular dependencies between modules
□ Docker Compose starts all services and passes health checks
□ Claim-to-cash lifecycle test: ingest claim → classify → AP → payment → settle → invoice → AR → pay → journal entries correct
□ FWA lifecycle test: ingest claim → flag by rule → create investigation → demand → recovery → journal entry
```

---

## 7. STRENGTHENED BUILDER SKILLS

Each builder's agent file must include these standard patterns (code snippets they can reference):

### 7.1 All Builders — Standard Patterns

**Decimal handling:**
```python
from decimal import Decimal, ROUND_HALF_UP

def money(value) -> Decimal:
    """Convert any numeric to Decimal with 2 decimal places."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def penny_allocate(total: Decimal, count: int) -> list[Decimal]:
    """Split total into count parts, allocating remainder penny to first item."""
    if count <= 0:
        return []
    per_item = (total / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    allocated = [per_item] * count
    remainder = total - sum(allocated)
    allocated[0] += remainder
    return allocated
```

**Tenant-scoped query:**
```python
async def get_claims(db: AsyncSession, tenant_id: UUID, filters: ClaimFilters):
    query = select(ClaimRecord).where(ClaimRecord.tenant_id == tenant_id)
    # NEVER omit tenant_id from any query
    ...
```

**Error response:**
```python
from core.exceptions import NotFoundError, ValidationError, ForbiddenError

# Standard error response: {"error": {"code": "NOT_FOUND", "message": "...", "field": "...", "correlation_id": "..."}}
# Raised in services, caught by FastAPI exception handlers in core
```

**Audit logging:**
```python
# Automatic via middleware for mutating requests
# Manual for specific business events:
await audit_service.log(
    tenant_id=tenant_id,
    user_id=current_user.id,
    action="payment_batch.approved",
    entity_type="payment_batch",
    entity_id=str(batch.id),
    after_value={"status": "approved", "total": str(batch.total_amount)},
    correlation_id=correlation_id,
)
```

**Event publishing:**
```python
await event_bus.publish(
    event_type="payment_batch.submitted",
    tenant_id=tenant_id,
    correlation_id=correlation_id,
    payload={"batch_id": str(batch.id), "vendor_config_id": str(batch.vendor_config_id)},
)
```

**Test pattern (TDD):**
```python
# 1. Write the test FIRST (RED)
async def test_fee_split_three_ways_allocates_remainder():
    total = Decimal("100.00")
    result = penny_allocate(total, 3)
    assert result == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
    assert sum(result) == total  # CRITICAL: must sum exactly

# 2. Implement the function (GREEN)
# 3. Refactor if needed (REFACTOR)
```

**Property-based test:**
```python
from hypothesis import given
from hypothesis.strategies import decimals, integers

@given(
    total=decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
    count=integers(min_value=1, max_value=1000),
)
def test_penny_allocate_always_sums_to_total(total, count):
    result = penny_allocate(total, count)
    assert sum(result) == total
    assert len(result) == count
    assert all(isinstance(r, Decimal) for r in result)
```

**Database advisory lock:**
```python
async def with_advisory_lock(db: AsyncSession, lock_key: str, timeout_seconds: int = 30):
    """Acquire a PostgreSQL advisory lock. Prevents concurrent batch generation."""
    lock_id = hash(lock_key) & 0x7FFFFFFF  # positive int32
    result = await db.execute(text(f"SELECT pg_try_advisory_lock({lock_id})"))
    if not result.scalar():
        raise ConflictError(f"Operation already in progress: {lock_key}")
    try:
        yield
    finally:
        await db.execute(text(f"SELECT pg_advisory_unlock({lock_id})"))
```

### 7.2 Builder-Specific Skill Additions

**Builder-Billing additional patterns:**
- `NACHA file structure` — batch header, entry detail, batch control, file control with hash calculation
- `835 segment structure` — ISA/GS/ST envelope, CLP/SVC loops, PLB adjustments
- `Invoice PDF generation` — ReportLab or WeasyPrint with tenant branding
- `Journal entry creation` — append-only function that calculates hash chain
- `State compliance table lookup` — query function that returns state-specific rules

**Builder-Payment-Processing additional patterns:**
- `Vendor adapter interface` — abstract base class with format/submit/poll/parse_return methods
- `OFAC screening function` — check entity against SDN list, return match/no-match
- `Business day calculation` — given a date, find next business day using holiday calendar
- `Retry with exponential backoff` — generic retry decorator with configurable max retries

**Builder-ReclaimRx additional patterns:**
- `Detection rule evaluator` — generic engine that takes a rule definition and a claim, returns flag/no-flag
- `XGBoost model training pipeline` — feature extraction, train/test split, evaluation metrics
- `Isolation Forest scoring` — anomaly detection on entity profiles
- `NetworkX community detection` — Louvain algorithm on pharmacy-prescriber-member graph
- `Recovery estimation` — three-tier calculation with methodology tagging

**Builder-Reporting additional patterns:**
- `Read replica connection` — SQLAlchemy engine configured for replica with failover
- `Materialized view refresh` — scheduled job that refreshes reporting views
- `Excel generation` — openpyxl with streaming for large datasets
- `PDF generation with branding` — WeasyPrint with tenant logo, colors, headers/footers
- `Dashboard widget data` — standard response format for chart/KPI/table widgets

---

## 8. DEFINITION OF DONE

### Task is DONE when:
- Tests written first (TDD verified by git history: test commit before implementation commit)
- All tests pass
- Coverage ≥ 99% for the task's code
- mypy strict passes
- No lint errors
- Committed with descriptive message

### Session is DONE when:
- All assigned tasks complete
- QA sweeps pass
- Coverage ≥ 99% for the session's scope
- Handoff note written (if session ended due to context)

### Module is DONE when:
- Every section of PRD implemented
- Module-level gate passes (section 6.3)
- README complete
- Can start independently via Docker Compose

### Phase is DONE when:
- All modules done
- Merged successfully
- Phase-level gate passes (section 6.4)
- Claim-to-cash lifecycle test passes end-to-end

---

## 9. ANTI-PATTERNS (What Builders Must NEVER Do)

| Anti-Pattern | Why It's Bad | What To Do Instead |
|---|---|---|
| Write code then tests | Confirms implementation, not behavior | TDD: test first, then implement |
| `# type: ignore` | Hides type errors | Fix the type annotation |
| `# noqa` | Hides lint errors | Fix the lint issue |
| `except Exception: pass` | Swallows errors silently | Catch specific exceptions, log them |
| `float(amount)` | Financial precision loss | `Decimal(str(amount))` |
| Raw SQL with f-strings | SQL injection | Parameterized queries via SQLAlchemy |
| `print()` for debugging | Not structured, not searchable | `logger.debug()` with structured data |
| Skip failing test | Hides bugs | Fix the code or fix the test |
| Hardcode tenant_id | Breaks multi-tenancy | Always from request context |
| Copy-paste service logic | Maintenance nightmare | Extract to shared utility in core/ |
| Comment out broken code | Dead code accumulation | Delete it. Git has history. |
| Test implementation details | Fragile tests | Test behavior (inputs → outputs) |
| Mock everything | Tests pass but code is broken | Use real DB for integration tests |

---

## 10. TOOLCHAIN

```
# Python
Python 3.13
FastAPI 0.135.x
SQLAlchemy 2.x (async)
Alembic (migrations)
Pydantic 2.x (validation)
pytest + pytest-asyncio + pytest-cov
hypothesis (property-based testing)
factory_boy (test data factories)
httpx (TestClient)
ruff (lint + format — replaces flake8+black, 10-100x faster)
mypy --strict (type checking)
safety (dependency CVE scanning)

# Database
PostgreSQL 17
Redis 7.4
RabbitMQ 4

# File generation
openpyxl (Excel — streaming mode for large files)
WeasyPrint or ReportLab (PDF)
python-pptx (not needed Phase 2)

# ML (ReclaimRx only)
scikit-learn (XGBoost wrapper, Isolation Forest)
networkx (graph analysis, community detection)
numpy (feature arrays — never for money)

# Infrastructure
Docker + Docker Compose
Terraform (Azure deployment)
```
