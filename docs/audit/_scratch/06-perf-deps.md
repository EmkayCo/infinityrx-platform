# Performance / Dependencies & Version Currency — Audit Findings

---

## Category 11: Performance & Scalability — score: 52/100

### Findings

#### Database Indexes
- **12 model files** across modules; all have indexes defined. Counts:
  - reclaimrx: 36 indexes / 27 tables — good density
  - dataiq: 24 / 11; pharmacy-directory: 24 / 10; member-management: 20 / 8 — adequate
  - billing: 14 / 25 — **underconfigured**: 25 tables with only 14 indexes; multiple status and FK columns likely missing tenant+status composite indexes
  - prescriber-directory: 13 / 7 — acceptable
  - edi-compliance: 11 / 8 — marginal
  - drug-database: 11 / 9 — marginal
  - medical-claims: 13 / 4 — acceptable
  - shared/db models (core, events, sessions) — not counted above
- Zero use of `selectinload` / `joinedload` anywhere in the codebase (grep returned 0 results). This is a **critical gap** — no eager loading is applied at all.

#### Connection Pooling
- `shared/db/engine.py` correctly uses `create_async_engine` with `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=1800`. Well-configured.
- **However**: billing, drug-database, and prescriber-directory modules each have **module-local sync session factories** using `psycopg2` (architecture violation per rules). These bypass the shared pool:
  - `modules/billing/src/db/session.py` — sync `create_engine`, no `pool_size`/`max_overflow` set
  - `modules/drug-database/src/db/session.py` — sync `create_engine`, no pool config
  - `modules/prescriber-directory/src/db/session.py` — sync `create_engine`, no pool config
  - `modules/payment-processing/src/_shim/db.py` — sync `create_engine`
  - `modules/reclaimrx/src/_shim/db.py` — sync `create_engine`
  - `modules/core-platform/src/_shim/db.py` — sync `create_engine`

#### N+1 / Eager Loading
- **Zero** `selectinload` / `joinedload` usages across all modules.
- `prescriber-directory` stats endpoint (`/stats`) fires **5 separate COUNT queries** in a single sync route (lines 352–356) — should be a single `CASE`/`filter` aggregate.
- No query counter test fixture exists anywhere — mandatory per performance rules.

#### Sync Routes Blocking the Event Loop
- **CRITICAL**: Multiple modules use sync `def` route handlers that execute synchronous SQLAlchemy DB calls directly on the event loop thread:
  - `modules/billing/src/api/router.py` — **0 async routes; 77 sync routes** with DB I/O
  - `modules/reclaimrx/src/api/router.py` — **0 async routes; 24 sync routes** with DB I/O (`db.execute`, `db.flush`, `db.commit`)
  - `modules/payment-processing/src/api/router.py` — 0 async / 19 sync routes
  - `modules/drug-database/src/api/router.py` — 0 async / 16 sync routes with DB I/O
  - `modules/prescriber-directory/src/api/router.py` — 1 async / 17 sync routes with sync DB access
  - `pharmacy-directory`: 5 sync helper routes (lower severity — DB-free helpers)
- At 100M claims/year, sync route handlers in an async FastAPI app will serialize request processing and cause cascading latency under load.

#### Redis Caching
- `drug-database` service: Redis caching implemented with TTL and invalidation — correct.
- `member-management` eligibility service: Redis caching with TTL and invalidation — correct.
- `pharmacy-directory` lookup service: Redis (`PharmacyCache`) with `get_by_npi`/`set_by_npi` — correct.
- **Gaps**: `prescriber-directory` uses **in-memory dict cache** only (taxonomy service comment), no Redis. No NPI-level Redis caching for prescriber lookups.
- No Redis caching visible in `billing`, `reclaimrx`, or `payment-processing` for reference data.

#### Slow Query Logging
- `shared/observability/slow_query.py` implements `install_slow_query_logger` at 1000ms threshold (matches `log_min_duration_statement=1000` in docker-compose) — good.
- **Only `core-platform/src/main.py` installs it.** All other modules (`billing`, `drug-database`, `member-management`, `prescriber-directory`, `dataiq`, `edi-compliance`, `medical-claims`) **do not** install the slow query logger. Application-side slow query detection is absent for 7+ modules.

#### `statement_timeout`
- **Not configured** anywhere in `shared/db/engine.py` or any module-local session factory. Docker-side `log_min_duration_statement=1000` logs slow queries post-hoc but does not abort them. A runaway query can block a connection indefinitely.
- Required by performance rules: `MUST have statement_timeout configured`.

#### Batch Operations
- `billing` models include `payment_batches` table with batch-level endpoints — batch processing is modeled.
- `drug-database` has `batch_lookup` endpoint.
- No `bulk_insert_mappings` or `bulk_save_objects` patterns observed; SQLAlchemy 2.x `insert().values(...)` preferred approach not confirmed in use.

#### Event Bus At-Least-Once Delivery
- `shared/events/rabbitmq_bus.py`: `publisher_confirms=True`; consumer `await message.ack()` after successful processing; retry-with-backoff before DLQ. At-least-once delivery is correctly implemented.

#### Read Replica for Analytics
- `reporting/src/services/report_engine.py` accepts optional `read_replica_session`; falls back to primary if not provided. Architecture is present; wiring at the FastAPI dependency level not confirmed.

### Issues (Ranked by Severity)

| # | Severity | Issue |
|---|---|---|
| P11-01 | CRITICAL | 77+ route handlers across billing/reclaimrx/payment-processing/drug-database/prescriber-directory are sync `def` with synchronous DB I/O — blocks asyncio event loop under load |
| P11-02 | CRITICAL | `statement_timeout` not configured on any engine — runaway queries can exhaust connection pool |
| P11-03 | HIGH | Zero `selectinload`/`joinedload` usage — every relationship traversal risks N+1 at 100M claims/year scale |
| P11-04 | HIGH | Slow query logger only installed in `core-platform`; 7 other modules have no application-level slow query detection |
| P11-05 | HIGH | 3 modules + 3 `_shim` files use module-local sync session factories (architecture violation) — bypass shared pool config and tenant isolation layer |
| P11-06 | MEDIUM | Prescriber stats endpoint: 5 sequential `COUNT` queries per request — should be single aggregate |
| P11-07 | MEDIUM | No query counter test fixture anywhere — N+1 regressions cannot be caught in CI |
| P11-08 | MEDIUM | `prescriber-directory` NPI lookups not Redis-cached; only in-memory taxonomy cache |
| P11-09 | LOW | `billing` has 25 tables with only 14 indexes — tenant+status composite indexes likely missing |

### Recommendations

1. Convert all sync route handlers in billing, reclaimrx, payment-processing, drug-database, and prescriber-directory to `async def` and replace sync session factories with `shared.db.session.get_session`.
2. Add `connect_args={"options": "-c statement_timeout=30000"}` to `shared/db/engine.py` (30s ceiling; tune per endpoint via `execution_options`).
3. Add `selectinload`/`joinedload` for every ORM relationship traversal; audit each service for N+1.
4. Add `install_slow_query_logger` to every module's `create_app()` / lifespan.
5. Add a `query_counter` pytest fixture to `shared/tests/conftest.py` and use it in integration tests.
6. Eliminate module-local session factories — redirect all modules to `shared.db.session`.
7. Add Redis caching for prescriber NPI lookups.
8. Consolidate prescriber stats to a single SQL aggregate query.

---

## Category 12: Dependencies & Version Currency — score: 74/100

### Version Currency Table

| Software | Version Pinned (pyproject) | Version Installed | Latest Stable 2026-04 | Status | Notes |
|---|---|---|---|---|---|
| Python | `>=3.13,<3.14` | 3.13.13 | 3.14.4 | ACCEPTABLE | Pinned to 3.13; 3.14 is available. Intentional `<3.14` constraint. |
| PostgreSQL | `17` (docker-compose) | 17 (docker) | 17.x (18 released Sept 2025) | ✓ | 17 still widely used; acceptable |
| Redis | `7.4` (docker-compose) | 7.4.0 | 8.0 | ACCEPTABLE | 8.0 available; 7.4 LTS still supported |
| RabbitMQ | `4-management` (docker) | 4.x | 4.x | ✓ | Not pinned to patch — minor risk |
| FastAPI | `>=0.115` | 0.135.3 | ~0.115+ | ✓ | Well ahead of minimum constraint |
| SQLAlchemy | `>=2.0.36` | 2.0.49 | 2.0.x | ✓ | Current |
| Pydantic | `>=2.10` | 2.12.5 | 2.x | ✓ | Current |
| Alembic | `>=1.14` | 1.18.4 | 1.x | ✓ | Current |
| Uvicorn | `>=0.32` | 0.44.0 | ~0.44 | ✓ | Current |
| asyncpg | `>=0.30` | 0.31.0 | 0.31.x | ✓ | Current |
| cryptography | `>=44.0` | 46.0.7 | ~46 | ✓ | Current |
| aio-pika | `>=9.5` | 9.6.2 | ~9.6 | ✓ | Current |
| redis (client) | `>=5.2` | 7.4.0 | ~7.x | ✓ | Current |
| xgboost | `>=3.2.0` | 3.2.0 | 3.2.x | ✓ | Current |
| scikit-learn | `>=1.8.0` | 1.8.0 | 1.8.x | ✓ | Current |
| openai | `>=1.50` | 2.31.0 | 2.x | ✓ | Current |
| psycopg2-binary | `>=2.9.11` | 2.9.11 | 2.9.x (psycopg3 preferred) | WARN | Deprecated for new code; psycopg3 (`psycopg[binary]`) recommended |
| Dockerfile Python | `3.13-slim` | — | `3.13.13-slim` or `3.13-slim` | WARN | Not pinned to specific patch digest; `FROM python:3.13-slim` floats on patch bumps |
| RabbitMQ docker | `4-management` | — | `4.x-management` | WARN | Not pinned to minor/patch — could receive breaking minor update |
| numpy | `>=1.26` | 2.4.4 | 2.x | ✓ | Jumped major; confirm compatibility |

### CVE Scan Results

```
uv run pip-audit result (2026-04-14):
  No known vulnerabilities found
  (infinityrx-platform skipped — not on PyPI)
```

**Clean — no CVEs in any installed dependency.**

### License Audit

| Package | License | Risk |
|---|---|---|
| numpy | BSD-3-Clause, 0BSD, MIT, Zlib, CC0-1.0 | None |
| pydantic | MIT | None |
| fastapi | MIT | None |
| sqlalchemy | MIT | None |
| cryptography | Apache-2.0 OR BSD-3-Clause | None |
| networkx | BSD-3-Clause (confirmed from PyPI metadata) | None |
| xgboost | Apache-2.0 (confirmed from PyPI metadata) | None |
| scikit-learn | BSD-3-Clause (confirmed from PyPI metadata) | None |

No GPL or AGPL licensed packages detected. License posture is clean.

### Unused / Heavyweight Dependencies Analysis

| Package | Size | Actual Usage | Status |
|---|---|---|---|
| `xgboost` | Large (C++ extension) | `modules/reclaimrx/src/services/ml_scoring.py` — `XGBClassifier` | ✓ Used |
| `networkx` | Medium | `modules/reclaimrx/src/services/graph_analysis.py` — `import networkx as nx` | ✓ Used |
| `pgvector` | Small | `modules/ai-nlp/src/models/tables.py` — `from pgvector.sqlalchemy import Vector` | ✓ Used |
| `scikit-learn` | Large | `modules/reclaimrx/src/services/ml_scoring.py` (transitive via xgboost) + direct scoring | ✓ Used |
| `psycopg2-binary` | Medium | `billing`, `drug-database`, `prescriber-directory` sync sessions | WARN: should migrate to `asyncpg` or `psycopg3` |
| `numpy` | Large | Implicit via scikit-learn/xgboost; `>=1.26` pinned but 2.4.4 installed — major version jump | Monitor |

All heavyweight packages (`xgboost`, `scikit-learn`, `networkx`, `pgvector`) have confirmed production usage. No dead weight.

### Additional Dependency Concerns

1. **`psycopg2-binary` in production**: The package is deprecated in favour of `psycopg` (psycopg3). It is only present because billing/drug-database/prescriber-directory use sync SQLAlchemy with psycopg2 driver. Migrating those modules to async eliminates the dependency.

2. **`pyproject.toml` duplicate `[dev]` group**: `[project.optional-dependencies] dev` and `[dependency-groups] dev` both define dev dependencies (`pytest` etc. in optional-deps, `hypothesis` in dependency-groups). This is not a strict error but can cause confusion about which is the authoritative dev dependency list.

3. **`uv.lock` present**: 1,694 lines — confirms full lock file exists. Reproducible builds are guaranteed.

4. **Docker image tags not pinned to digest**: `postgres:17`, `redis:7.4`, `rabbitmq:4-management` use floating tags. For a $300M/yr platform these should be digest-pinned (e.g., `postgres:17@sha256:...`) to prevent supply-chain drift in CI/CD.

5. **Dockerfile Python tag not digest-pinned**: `FROM python:3.13-slim` floats on patch releases. Should pin to `python:3.13.13-slim` at minimum, or digest.

6. **Python 3.14 not yet adopted**: `pyproject.toml` explicitly restricts `<3.14`. Python 3.14 was released Oct 2025. A migration window should be planned; the constraint prevents accidental 3.14 incompatibilities from surfacing but also defers access to performance improvements (freethreading, etc.).

7. **`numpy` major version drift**: pinned `>=1.26` but installed 2.4.4 — a major version jump. All numpy-consuming code should be verified against numpy 2.x API changes (array copy semantics, dtype changes).

### Recommendations

1. Pin Docker images to minor+patch tags (`postgres:17.4`, `redis:7.4.2`, `rabbitmq:4.0-management`) or SHA digest for supply-chain integrity.
2. Pin Dockerfile `FROM python:3.13.13-slim`.
3. Migrate billing/drug-database/prescriber-directory sync sessions to async (`asyncpg`) and drop `psycopg2-binary` from production dependencies.
4. Consolidate the two `[dev]` dependency sections into one (`[dependency-groups]` is the modern uv approach).
5. Plan Python 3.14 upgrade path — test suite should run against 3.14 in CI before adopting.
6. Tighten `numpy` lower bound to `>=2.0` to prevent accidental installs of numpy 1.x (which is incompatible with 2.x API changes already in use).
7. Add `pip-audit` to CI gate — currently clean but must stay clean.
