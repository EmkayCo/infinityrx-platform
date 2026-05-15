# Drug Database Module

FastAPI service providing NDC lookup, drug pricing, interaction checking, therapeutic equivalence, FDA/NADAC data ingestion, REMS tracking, drug shortage tracking, and multi-tenant MAC list overrides.

## Capabilities

- **NDC Normalization** — Converts 10-digit, 11-digit, and dashed NDC formats (5-4-2, 4-4-2, 5-3-2, 5-4-1) to canonical 11-digit. Rejects trailing newlines per LESSON-004.
- **Drug Lookup** — Single and batch NDC lookups with Redis caching (24hr TTL, tenant-scoped keys).
- **Drug Search** — Full-text search by name with filters for `drug_type` and `marketing_status`.
- **Pricing** — Effective-date-based price resolution with tenant pricing override precedence. All prices use `Decimal` with `ROUND_HALF_UP`.
- **Interactions** — Drug–drug interaction checking by NDC pairs, severity-sorted results.
- **Therapeutic Equivalence** — Orange Book TE code lookups.
- **MAC List Upload** — Tenant CSV upload for Maximum Allowable Cost overrides; validates all rows and reports every error before rejecting.
- **REMS Programs** — Per-NDC REMS requirement lookup.
- **Drug Shortages** — FDA shortage tracking with status filter.
- **FDA NDC Parser** — Ingests FDA NDC JSON/CSV exports.
- **NADAC Parser** — Ingests CMS NADAC pricing CSV.
- **FDB Adapter** — `FDBLocalDropAdapter` reads operator-managed NDDF Plus drops at `data/reference/fdb/TEL251759D/`. Generic `TableSpec`-driven surface (SPEC §3.7.2): `discover_latest_drop` / `open_table` / `parse_table`. Phase 8 TableSpec values: `RNP3_NDC_PRICE` (+ UPD variant), `RPRDPTD0_PRICE_TYPE_DESC`, `RNPTYPD0_NDC_PRICE_TYPE_DESC`. Hot-path `parse_rnp3` typed wrapper for the ingester's main loop.
- **Rate Limiting** — Token-bucket per-tenant rate limiter (`RateLimitMiddleware`), returns `429` with `Retry-After` header when exhausted.
- **Security Headers** — `SecurityHeadersMiddleware` mounted on all responses.
- **DLQ Router** — Dead-letter queue API mounted at `/api/v1/events/dlq`.

## Tech Stack

Python 3.13 | FastAPI | SQLAlchemy (async-compatible, PostgreSQL in prod / SQLite for tests) | Redis (caching) | Pydantic v2

## Running Tests

```bash
cd modules/drug-database
python3.13 -m pytest tests/ --cov=src --cov-branch
```

Coverage threshold: 99% branch coverage. Financial, PHI, security, and auth paths require 100%.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/drugs/health` | Health check |
| GET | `/api/v1/drugs/lookup/{ndc}` | Single NDC lookup |
| POST | `/api/v1/drugs/lookup/batch` | Batch NDC lookup |
| GET | `/api/v1/drugs/search` | Search by name (+ drug_type, marketing_status filters) |
| GET | `/api/v1/drugs/pricing/{ndc}` | Effective pricing for NDC |
| GET | `/api/v1/drugs/pricing/{ndc}/history` | Full pricing history |
| GET | `/api/v1/drugs/interactions` | Check NDC pairs for interactions |
| GET | `/api/v1/drugs/equivalents/{ndc}` | Therapeutic equivalents |
| POST | `/api/v1/drugs/overrides/upload` | Upload tenant MAC list CSV |
| GET | `/api/v1/drugs/overrides` | List tenant pricing overrides |
| DELETE | `/api/v1/drugs/overrides/{id}` | Delete a pricing override |
| GET | `/api/v1/drugs/rems/{ndc}` | REMS program for NDC |
| GET | `/api/v1/drugs/shortages` | List drug shortages (optional `?status=` filter) |
| GET | `/api/v1/drugs/shortages/{ndc}` | Shortages for specific NDC |
| GET | `/api/v1/drugs/refresh/status` | Data refresh log |

## Database Schema

Schema: `drug_database` (PostgreSQL). Tables: `drug_products`, `drug_pricing`, `drug_pricing_history`, `drug_interactions`, `therapeutic_equivalence`, `tenant_pricing_overrides`, `data_refresh_logs`, `drug_shortages`, `rems_programs`.

## Package layout

The Python package under `modules/drug-database/` has been through one structural rename:

| Era | Import path | Location |
|---|---|---|
| Pre-B8 (Phase 11A and earlier) | `from src.X import …` with module root on `sys.path` | `modules/drug-database/src/` |
| Post-B8 (Phase 11B onward) | `from drug_database.X import …` | `modules/drug-database/drug_database/` |

**Post-B8 details:**

- `[tool.setuptools.packages.find]` in `pyproject.toml` uses `where = ["."]` and
  `include = ["drug_database*"]` — all subpackages are discovered automatically.
- The module root (`modules/drug-database/`) must be on `sys.path` for the package
  to resolve; `conftest.py` and runtime callers inject this via `sys.path.insert`.
- Cross-module consumers (e.g. `adjudication-engine/src/services/pricing_enrichment.py`)
  import as `from drug_database.services.X import …` — no `type: ignore` shims required.
- The `src/` directory no longer exists. Any `from src.X` import will fail with
  `ModuleNotFoundError` at collection time — this is intentional (fail-fast over
  silent dual-identity).

## Lessons Applied

- **LESSON-001**: SAVEPOINT-based test isolation for all tests that call `db.commit()`.
- **LESSON-004**: NDC validation uses `re.fullmatch` and strips only spaces/tabs before checking for embedded newlines.
- **LESSON-005**: Logger `extra={}` keys prefixed with `svc_name`, `drug_ndc` to avoid `LogRecord` collisions.
- **LESSON-006**: All middleware and routers verified through `create_app()` integration tests.
